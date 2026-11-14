# SketchUp API จำลองขั้นต่ำ — ใช้ทดสอบว่าโค้ดเรียก API ครบและไม่ error (ไม่ได้จำลองเรขาคณิตจริง)
require 'json'
INCH = 0.0254
class Numeric
  def m; self / INCH; end
  def to_l; to_f; end # Length ของ SketchUp คือ Float หน่วยนิ้ว
  def to_m; self * INCH; end
end

module Geom
  class Vector3d
    attr_reader :x, :y, :z
    def initialize(x = 0, y = 0, z = 0) @x, @y, @z = x.to_f, y.to_f, z.to_f end
    def cross(o) Vector3d.new(y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x) end
    def length; Math.sqrt(x * x + y * y + z * z) end
    def normalize; l = length; Vector3d.new(x / l, y / l, z / l) end
    def normalize!; v = normalize; @x, @y, @z = v.x, v.y, v.z; self end
    def parallel?(o) cross(o).length < 1e-9 end
    def to_a; [x, y, z] end
  end
  class Point3d
    attr_reader :x, :y, :z
    def initialize(x = 0, y = 0, z = 0)
      x, y, z = x if x.is_a?(Array)
      @x, @y, @z = x.to_f, y.to_f, z.to_f
    end
    def to_a; [x, y, z] end
    def vector_to(o) Vector3d.new(o.x - x, o.y - y, o.z - z) end
    def distance(o) vector_to(o).length end
    def transform(t) t.apply(self) end
  end
  def self.linear_combination(a, p, b, q) Point3d.new(a * p.x + b * q.x, a * p.y + b * q.y, a * p.z + b * q.z) end
  class Transformation
    attr_reader :m # 3x4
    def initialize(arg = nil)
      @m = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]
      if arg.is_a?(Point3d) then @m[0][3], @m[1][3], @m[2][3] = arg.x, arg.y, arg.z end
    end
    def self.raw(m) t = new; t.instance_variable_set(:@m, m); t end
    def self.axes(o, x, y, z) raw([[x.x, y.x, z.x, o.x], [x.y, y.y, z.y, o.y], [x.z, y.z, z.z, o.z]]) end
    def self.translation(p) new(p.is_a?(Point3d) ? p : Point3d.new(*p.to_a)) end
    def self.rotation(o, ax, a)
      c = Math.cos(a); s = Math.sin(a)
      translation(o) * raw([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0]]) * translation(Point3d.new(-o.x, -o.y, -o.z))
    end
    def origin; Point3d.new(m[0][3], m[1][3], m[2][3]) end
    def apply(p) Point3d.new(*(0..2).map { |i| m[i][0] * p.x + m[i][1] * p.y + m[i][2] * p.z + m[i][3] }) end
    def *(o)
      r = (0..2).map do |i|
        (0..3).map { |j| (0..2).inject(0) { |s, k| s + m[i][k] * o.m[k][j] } + (j == 3 ? m[i][3] : 0) }
      end
      Transformation.raw(r)
    end
    def inverse # เฉพาะ translation/rotation
      rt = (0..2).map { |i| (0..2).map { |j| m[j][i] } }
      tt = (0..2).map { |i| -(0..2).inject(0) { |s, k| s + rt[i][k] * m[k][3] } }
      Transformation.raw((0..2).map { |i| rt[i] + [tt[i]] })
    end
  end
end
ORIGIN = Geom::Point3d.new; X_AXIS = Geom::Vector3d.new(1, 0, 0)
Y_AXIS = Geom::Vector3d.new(0, 1, 0); Z_AXIS = Geom::Vector3d.new(0, 0, 1)

module Sketchup
  class Color; def initialize(*a) @a = a end; attr_accessor :alpha; end
  class Entity
    def initialize; @attrs = {}; end
    def set_attribute(d, k, v) (@attrs[d] ||= {})[k] = v end
    def get_attribute(d, k, default = nil) (@attrs[d] || {}).fetch(k, default) end
    def attribute_dictionary(d) @attrs[d] end
    def valid?; true end
  end
  class Layer < Entity; attr_reader :name; def initialize(n) super(); @name = n end; def visible?; true end; end
  class Material < Entity
    attr_reader :name; attr_accessor :color, :alpha
    def initialize(n) super(); @name = n end
    def display_name; name end
  end
  class Vertex; attr_reader :position; def initialize(p) @position = p end; end
  class Edge < Entity
    attr_reader :start, :end
    def initialize(a, b) super(); @start = Vertex.new(a); @end = Vertex.new(b) end
    def faces; [] end
    def vertices; [@start, @end] end
  end
  class Face < Entity
    attr_reader :pts
    def initialize(pts) super(); @pts = pts end
    def followme(path) $followme += 1; @parent.extra << Face.new([]); true end
    def parent=(p) @parent = p end
    def normal; Geom::Vector3d.new(0, 0, -1) end
    def reverse!; self end
    def pushpull(d) $pushpull += 1 end
    def area(_t = nil) 1.0 end
    def erase!; @parent.list.delete(self) end
  end
  class Entities
    include Enumerable
    attr_reader :list, :extra
    def initialize; @list = []; @extra = []; end
    def each(&b) (@list + @extra).each(&b) end
    def add_group; g = Group.new; @list << g; g end
    def add_face(pts)
      raise 'face needs 3 points' if pts.size < 3
      raise 'face points must be Point3d' unless pts.all? { |p| p.is_a?(Geom::Point3d) }
      f = Face.new(pts); f.parent = self; @list << f; f
    end
    def add_curve(pts)
      raise 'curve points must be Point3d' unless pts.all? { |p| p.is_a?(Geom::Point3d) }
      e = (1...pts.size).map { |i| Edge.new(pts[i - 1], pts[i]) }; @list.concat(e); e
    end
    def add_instance(d, t) c = ComponentInstance.new(d); c.transformation = t; @list << c; c end
    def erase_entities(a) a.each { |x| @list.delete(x) } end
  end
  class Drawingelement < Entity
    attr_accessor :material, :layer, :name, :transformation
    def initialize; super(); @name = ''; @layer = Layer.new('Layer0'); @transformation = Geom::Transformation.new end
    def visible?; true end
    def volume; 100.0 end
  end
  class Group < Drawingelement
    attr_reader :entities
    def initialize; super(); @entities = Entities.new end
    def erase!; end
  end
  class ComponentDefinition; attr_reader :name, :entities; def initialize(n) @name = n; @entities = Entities.new end; end
  class ComponentInstance < Drawingelement
    attr_reader :definition
    def initialize(d) super(); @definition = d end
  end
  class Selection
    include Enumerable
    def initialize; @a = [] end
    def each(&b) @a.each(&b) end
    def clear; @a.clear end
    def add(*x) @a.concat(x.flatten) end
    def length; @a.size end
    def to_a; @a.dup end
    def first; @a.first end
  end
  class Collection
    include Enumerable
    def initialize(k) @k = k; @h = {} end
    def [](n) @h[n] end
    def add(n) @h[n] ||= @k.new(n) end
    def each(&b) @h.values.each(&b) end
  end
  class Model < Entity
    attr_reader :entities, :selection, :materials, :layers
    attr_accessor :tool
    def initialize; super(); @entities = Entities.new; @selection = Selection.new
      @materials = Collection.new(Material); @layers = Collection.new(Layer) end
    def active_entities; @entities end
    def title; 'ทดสอบ' end
    def start_operation(*) end
    def commit_operation; end
    def abort_operation; end
    def set_attribute(d, k, v) super end
    def select_tool(t) @tool = t end
  end
  class InputPoint
    attr_accessor :position
    def pick(*) end
  end
  @model = Model.new
  def self.active_model; @model end
  def self.require(p) Kernel.require(p.end_with?('.rb') ? p : "#{p}.rb") end
  def self.status_text=(s) end
end

module UI
  @answers = []
  class << self
    attr_accessor :answers, :messages
    def inputbox(prompts, defaults, *_rest) a = @answers.shift; a == :default ? defaults : a end
    def messagebox(m, *_) (@messages ||= []) << m; 6 end
    def menu(_) Menu.new end
    def savepanel(*) nil end
  end
  class Menu; def add_submenu(_) self end; def add_item(*) end; def add_separator; end; end
  class Command
    attr_accessor :tooltip, :status_bar_text, :small_icon, :large_icon
    def initialize(_t, &b) @b = b end
  end
  class Toolbar
    def initialize(_) end
    def add_item(_) end
    def add_separator; end
    def get_last_state; 0 end
    def show; end
    def restore; end
  end
end
TB_NEVER_SHOWN = -1; MB_YESNO = 4; IDYES = 6
$followme = 0; $pushpull = 0
def file_loaded?(_) false end
def file_loaded(_) end
