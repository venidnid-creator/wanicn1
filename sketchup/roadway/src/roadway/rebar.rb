# 3) เหล็กเสริม (แทน Toh Rebar): คาน เสา พื้น/ฐานราก และเหล็กตามแนว
module WanicnSurvey
  module RoadWay
    module Rebar
      module_function

      STYLES = %w[ท่อ\ 3\ มิติ เส้นศูนย์กลาง\ (เร็ว)].freeze
      COLORS = { 6 => [230, 160, 40], 9 => [220, 120, 40], 10 => [200, 60, 60], 12 => [180, 40, 40],
                 16 => [150, 40, 120], 20 => [90, 60, 170], 25 => [40, 90, 170], 28 => [30, 130, 140],
                 32 => [30, 140, 80] }.freeze

      # ---------- เครื่องมือคลิกจุดวาง ----------
      class PickTool
        def initialize(prompt, &cb)
          @prompt = prompt
          @cb = cb
          @ip = Sketchup::InputPoint.new
        end

        def activate
          Sketchup.status_text = @prompt
        end

        def onMouseMove(_flags, x, y, view)
          @ip.pick(view, x, y)
          view.tooltip = @ip.tooltip
          view.invalidate
        end

        def onLButtonDown(_flags, x, y, view)
          @ip.pick(view, x, y)
          pt = @ip.position
          Sketchup.active_model.select_tool(nil)
          @cb.call(pt)
        end

        def draw(view)
          @ip.draw(view) if @ip.valid?
        end

        def onCancel(_reason, _view)
          Sketchup.active_model.select_tool(nil)
        end
      end

      def pick(prompt, &cb)
        Sketchup.active_model.select_tool(PickTool.new(prompt, &cb))
      end

      # แกนท้องถิ่น: x = ทิศ dir, z ใกล้แนวดิ่ง
      def axes_along(origin, dir)
        x = dir.normalize
        y = Z_AXIS.cross(x)
        y = Y_AXIS if y.length < 1e-9
        y.normalize!
        Geom::Transformation.axes(origin, x, y, x.cross(y))
      end

      # ---------- คำสั่ง ----------

      def beam
        sel = Sketchup.active_model.selection
        edge = sel.length == 1 ? sel.grep(Sketchup::Edge).first : nil
        r = RoadWay.ask(:rb_beam,
                        ['รหัสคาน', 'กว้าง b (ม.)', 'ลึก h (ม.)', 'ยาว L (ม.) (ถ้าเลือกเส้นจะใช้ความยาวเส้น)',
                         'ระยะหุ้ม (ม.)', 'เหล็กบน', 'เหล็กล่าง', 'เหล็กปลอก', 'แสดงเหล็กแบบ'],
                        ['B1', '0.20', '0.40', '4.00', RebarCalc::COVER['beam'].to_s,
                         '2-DB12', '2-DB12', 'RB6@0.15', STYLES[0]],
                        ['', '', '', '', '', '', '', '', STYLES.join('|')],
                        'RoadWay — เหล็กเสริมคาน') or return
        len = edge ? edge.length.to_m : r[3].to_f
        res = calc { RebarCalc.beam(mark: r[0], b: r[1].to_f, h: r[2].to_f, L: len, cover: r[4].to_f,
                                    top: r[5], bot: r[6], stirrup: r[7]) } or return
        box = [[0, -r[1].to_f / 2, -r[2].to_f], [len, r[1].to_f / 2, 0]]
        if edge
          tr = axes_along(edge.start.position, edge.start.position.vector_to(edge.end.position))
          build(res, box, tr, r[8])
        else
          pick('คลิกจุดเริ่มคาน (ระดับหลังคาน) — คานวางตามแกนแดง') do |pt|
            build(res, box, Geom::Transformation.new(pt), r[8])
          end
        end
      end

      def column
        r = RoadWay.ask(:rb_column,
                        ['รหัสเสา', 'กว้าง (แกนแดง) (ม.)', 'ลึก (แกนเขียว) (ม.)', 'สูง (ม.)', 'ระยะหุ้ม (ม.)',
                         'เหล็กยืน', 'เหล็กปลอก', 'เผื่อระยะทาบด้านบน', 'แสดงเหล็กแบบ'],
                        ['C1', '0.20', '0.20', '3.00', RebarCalc::COVER['column'].to_s,
                         '4-DB12', 'RB6@0.15', 'ใช่', STYLES[0]],
                        ['', '', '', '', '', '', '', 'ใช่|ไม่', STYLES.join('|')],
                        'RoadWay — เหล็กเสริมเสา') or return
        res = calc { RebarCalc.column(mark: r[0], b: r[1].to_f, h: r[2].to_f, H: r[3].to_f, cover: r[4].to_f,
                                      main: r[5], tie: r[6], with_lap: r[7] == 'ใช่') } or return
        bx = r[1].to_f / 2; by = r[2].to_f / 2
        pick('คลิกจุดศูนย์กลางโคนเสา') do |pt|
          build(res, [[-bx, -by, 0], [bx, by, r[3].to_f]], Geom::Transformation.new(pt), r[8])
        end
      end

      def slab
        r = RoadWay.ask(:rb_slab,
                        ['รหัส', 'ชนิด', 'ยาว (แกนแดง) (ม.)', 'กว้าง (แกนเขียว) (ม.)', 'หนา (ม.)', 'ระยะหุ้ม (ม.)',
                         'เหล็กแนวแกนแดง', 'เหล็กแนวแกนเขียว', 'ตะแกรงบนด้วย', 'แสดงเหล็กแบบ'],
                        ['S1', 'พื้น', '4.00', '4.00', '0.10', RebarCalc::COVER['slab'].to_s,
                         'RB9@0.20', 'RB9@0.20', 'ไม่', STYLES[0]],
                        ['', 'พื้น|ฐานราก', '', '', '', '', '', '', 'ใช่|ไม่', STYLES.join('|')],
                        'RoadWay — เหล็กเสริมพื้น/ฐานราก') or return
        footing = r[1] == 'ฐานราก'
        res = calc { RebarCalc.slab(mark: r[0], Lx: r[2].to_f, Ly: r[3].to_f, t: r[4].to_f, cover: r[5].to_f,
                                    bars_x: r[6], bars_y: r[7], top: r[8] == 'ใช่', footing: footing) } or return
        pick("คลิกมุมล่างซ้ายของ#{r[1]} (ระดับท้อง#{r[1]})") do |pt|
          build(res, [[0, 0, 0], [r[2].to_f, r[3].to_f, r[4].to_f]], Geom::Transformation.new(pt), r[9])
        end
      end

      def along_path
        path = RoadWay.selected_path or return
        r = RoadWay.ask(:rb_path, ['รหัสเหล็ก', 'ขนาดเหล็ก', 'จำนวนเส้น (ชุดเดียวกัน)', 'แสดงเหล็กแบบ'],
                        ['R1', 'DB12', '1', STYLES[0]], ['', '', '', STYLES.join('|')],
                        'RoadWay — เหล็กตามแนว') or return
        b = calc { RebarCalc.parse!(r[1], nil) } or return
        pts = path[:points]
        RoadWay.operation('RoadWay: เหล็กตามแนว') do
          len = Sweep.length_m(pts)
          g = add_bar(Sketchup.active_model.active_entities, b[:d], pts, r[3])
          g.name = "#{r[0]} #{b[:text]}"
          RoadWay.stamp(g, kind: 'rebar', mark: r[0], bar: b[:text], bar_kind: b[:kind], dia_mm: b[:d],
                           length_m: len.round(3), shape: 'ตามแนว', count: [r[2].to_i, 1].max,
                           kg: (len * RebarCalc.kg_m(b[:d]) * [r[2].to_i, 1].max).round(3))
        end
      end

      # ---------- สร้างในโมเดล ----------

      def calc
        yield
      rescue ArgumentError => e
        UI.messagebox(e.message)
        nil
      end

      def bar_material(d)
        RoadWay.material("RW-เหล็ก Ø#{d}", Sketchup::Color.new(*(COLORS[d] || [120, 120, 120])))
      end

      def add_bar(ents, d, pts, style)
        if style == STYLES[1]
          g = ents.add_group
          g.entities.add_curve(pts)
        else
          g = Sweep.sweep(ents, [Profiles.circle(d / 2000.0, 8)], pts)
        end
        g.material = bar_material(d)
        g
      end

      def build(res, box, tr, style)
        RoadWay.operation("RoadWay: #{res[:mark]}") do
          model = Sketchup.active_model
          root = model.active_entities.add_group
          root.name = "#{label(res[:kind])} #{res[:mark]}"
          ents = root.entities
          conc = ents.add_group
          conc.name = "คอนกรีต #{res[:mark]}"
          (x0, y0, z0), (x1, y1, z1) = box
          f = conc.entities.add_face([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]].map { |p| Geom::Point3d.new(*p.map(&:m)) })
          f.reverse! if f.normal.z < 0 # ให้หน้าชี้ขึ้น แล้วดันขึ้นเป็นความสูง
          f.pushpull((z1 - z0).m)
          mat = RoadWay.material('RW-คอนกรีต', Sketchup::Color.new(170, 170, 165))
          mat.alpha = 0.35
          conc.material = mat
          RoadWay.stamp(conc, kind: 'concrete', mark: res[:mark], element: res[:kind],
                              volume_m3: res[:concrete_m3].round(4), form_m2: res[:form_m2].round(3))
          res[:bars].each do |b|
            pts = b[:pts].map { |p| Geom::Point3d.new(*p.map(&:m)) }
            g = add_bar(ents, b[:d], pts, style)
            g.name = "#{b[:mark]} #{b[:bar]}"
            RoadWay.stamp(g, kind: 'rebar', mark: b[:mark], bar: b[:bar], bar_kind: b[:kind],
                             dia_mm: b[:d], length_m: b[:length], shape: b[:shape], count: 1,
                             kg: (b[:length] * RebarCalc.kg_m(b[:d])).round(3))
          end
          root.transformation = tr
          root.layer = RoadWay.tag('RW-โครงสร้าง')
          RoadWay.stamp(root, kind: 'element', mark: res[:mark], element: res[:kind])
          model.selection.clear
          model.selection.add(root)
          root
        end
      end

      def label(kind)
        { 'beam' => 'คาน', 'column' => 'เสา', 'slab' => 'พื้น', 'footing' => 'ฐานราก' }.fetch(kind, kind)
      end
    end
  end
end
