# ทดสอบเส้นทางโค้ดทั้งหมดกับ SketchUp API จำลอง:  ruby test/test_smoke.rb
require 'minitest/autorun'
require_relative 'sketchup_stub'
$LOADED_FEATURES << 'sketchup.rb' << 'extensions.rb'
module WanicnSurvey; module RoadWay; VERSION = 'test'; PLUGIN_NAME = 'RoadWay'; end; end
require_relative '../src/roadway/core'
RW = WanicnSurvey::RoadWay

class TestSmoke < Minitest::Test
  def model; Sketchup.active_model end

  def setup
    model.entities.list.clear
    model.selection.clear
    UI.messages = []
    RW.instance_variable_set(:@memory, {})
  end

  def click(pt)
    tool = model.tool
    assert tool, UI.messages.inspect
    tool.instance_variable_get(:@ip).position = pt
    tool.onLButtonDown(0, 0, 0, nil)
  end

  def path_edges(pts)
    model.entities.add_curve(pts.map { |p| Geom::Point3d.new(*p.map(&:m)) })
  end

  def connect(edges)
    # ให้ปลายเส้นที่ติดกันใช้ Vertex เดียวกัน (เหมือน SketchUp)
    (1...edges.size).each { |i| edges[i].instance_variable_set(:@start, edges[i - 1].end) }
    edges.each { |e| def e.used_by?(v) vertices.include?(v) end; def e.other_vertex(v) v == start ? self.end : start end }
    edges
  end

  def test_profile_along_path
    e = connect(path_edges([[0, 0, 0], [5, 0, 0], [5, 5, 0]]))
    model.selection.add(e)
    UI.answers = [:default, :default]
    g = RW::ProfileBuilder.run
    assert_kind_of Sketchup::Group, g, UI.messages.inspect
    i = RW.info(g)
    assert_equal 'profile', i['kind']
    assert_in_delta 10.0, i['length_m'], 1e-6
    assert_in_delta 0.01 * 10, i['volume_m3'], 1e-6
  end

  def test_road
    model.selection.add(connect(path_edges([[0, 0, 0], [100, 0, 0]])))
    UI.answers = [:default]
    road = RW::RoadBuilder.run
    assert road, UI.messages.inspect
    layers = road.entities.list.map { |g| RW.info(g) }
    assert_equal %w[ผิวทาง พื้นทาง รองพื้นทาง], layers.map { |x| x['label'] }
    assert_in_delta 800.0, layers[0]['area_m2'], 1e-6
    assert_in_delta 8 * 0.05 * 100, layers[0]['volume_m3'], 1e-6
  end

  def test_rebar_beam_column_slab_and_report
    UI.answers = [:default]; RW::Rebar.beam; click(ORIGIN)
    UI.answers = [:default]; RW::Rebar.column; click(Geom::Point3d.new(5.m, 0, 0))
    UI.answers = [:default]; RW::Rebar.slab; click(ORIGIN)
    assert_empty UI.messages
    assert_equal 3, model.entities.list.size
    d = RW::Quantifier.data
    JSON.generate(d) # ต้องแปลงเป็น JSON ได้
    labels = d[:tabs]['label'][:rows].map { |r| r[:name] }
    assert_includes labels, 'คอนกรีตคาน'
    assert_includes labels, 'เหล็ก DB12'
    assert d[:cut].any? { |r| r[:mark] == 'B1-S' }
    assert d[:cutsum][:kg] > 0
    beam_conc = d[:tabs]['label'][:rows].find { |r| r[:name] == 'คอนกรีตคาน' }
    assert_in_delta 0.32, beam_conc[:volume], 1e-6
  end

  def test_array_along
    defn = Sketchup::ComponentDefinition.new('เสาไฟ')
    inst = model.entities.add_instance(defn, Geom::Transformation.new)
    e = connect(path_edges([[0, 0, 0], [10, 0, 0], [10, 10, 0]]))
    model.selection.add(e + [inst])
    UI.answers = [%w[2.0 0 ใช่ ใช่]]
    RW::ProfileBuilder.array_along
    copies = model.entities.list.grep(Sketchup::ComponentInstance).select { |c| RW.info(c) }
    assert_equal 11, copies.size # 0,2,...,20
    last = copies.last.transformation.origin
    assert_in_delta 10.m, last.x, 1e-6
    assert_in_delta 10.m, last.y, 1e-6
  end

  def test_bad_bar_text_shows_thai_message
    UI.answers = [['B1', '0.20', '0.40', '4.00', '0.03', 'DB12', '2-DB12', 'RB6@0.15', 'ท่อ 3 มิติ']]
    assert_nil RW::Rebar.beam
    assert_match(/ต้องระบุจำนวน/, UI.messages.last)
  end
end
