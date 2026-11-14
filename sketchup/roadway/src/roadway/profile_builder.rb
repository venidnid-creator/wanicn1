# 1) ตัวสร้างโปรไฟล์ตามแนว (แทน Profile Builder)
module WanicnSurvey
  module RoadWay
    module ProfileBuilder
      module_function

      def run
        path = RoadWay.selected_path or return
        types = Profiles::CATALOG.keys
        names = types.map { |t| Profiles::CATALOG[t][:name] }
        r = RoadWay.ask(:pb_main,
                        ['หน้าตัด', 'จุดยึดกับแนว', 'หมุน (องศา)', 'เลื่อนแนวขวาง (ม.)',
                         'เลื่อนแนวตั้ง (ม.)', 'กลับด้าน', 'วัสดุ', 'Tag (เลเยอร์)'],
                        [names[0], 'กลาง', '0', '0', '0', 'ไม่', '(ไม่กำหนด)', 'RW-โปรไฟล์'],
                        [names.join('|'), Profiles::ANCHORS.join('|'), '', '', '', 'ไม่|ใช่',
                         RoadWay.material_names.join('|'), ''],
                        'RoadWay — โปรไฟล์ตามแนว') or return
        type = types[names.index(r[0])]
        spec = Profiles::CATALOG[type]
        dims = RoadWay.ask("pb_#{type}".to_sym,
                           spec[:params].map { |p| "#{p[0]} (ม.)" },
                           spec[:params].map { |p| p[1].to_s },
                           nil, "ขนาด — #{spec[:name]}") or return
        loops = Profiles.place(Profiles.build(type, dims), r[1], r[3].to_f, r[4].to_f,
                               r[2].to_f, r[5] == 'ใช่')
        label = "#{spec[:name]} #{dims.join('x')}"
        RoadWay.operation('RoadWay: โปรไฟล์ตามแนว') do
          model = Sketchup.active_model
          g = Sweep.sweep(model.active_entities, loops, path[:points], label, RoadWay.material(r[6]))
          g.layer = RoadWay.tag(r[7]) if RoadWay.tag(r[7])
          len = Sweep.length_m(path[:points])
          area = Profiles.area(loops)
          RoadWay.stamp(g, kind: 'profile', label: label, profile: type,
                           dims: dims.join('x'), length_m: len, section_m2: area,
                           volume_m3: area * len)
          model.selection.clear
          model.selection.add(g)
          g
        end
      end

      def from_face
        sel = Sketchup.active_model.selection
        faces = sel.grep(Sketchup::Face)
        if faces.size != 1
          UI.messagebox('เลือกหน้า (Face) ที่เป็นหน้าตัด 1 หน้า พร้อมเส้นแนว')
          return
        end
        face = faces[0]
        path = Sweep.ordered_path(sel.grep(Sketchup::Edge) - face.edges)
        unless path
          UI.messagebox('เส้นแนวต้องต่อเนื่องเส้นเดียว (ไม่นับขอบของหน้าตัด)')
          return
        end
        r = RoadWay.ask(:pb_face, ['ชื่อชิ้นส่วน', 'วัสดุ', 'Tag (เลเยอร์)'],
                        ['โปรไฟล์กำหนดเอง', '(ไม่กำหนด)', 'RW-โปรไฟล์'],
                        ['', RoadWay.material_names.join('|'), ''],
                        'RoadWay — โปรไฟล์จากหน้าที่เลือก') or return
        RoadWay.operation('RoadWay: โปรไฟล์จากหน้า') do
          model = Sketchup.active_model
          g = model.active_entities.add_group
          ents = g.entities
          ents.add_face(face.outer_loop.vertices.map(&:position))
          face.loops.reject(&:outer?).each do |lp|
            hf = ents.add_face(lp.vertices.map(&:position))
            hf.erase! if hf && hf.valid?
          end
          sect = ents.grep(Sketchup::Face).first
          curve = ents.add_curve(path[:points])
          sect.followme(curve) or raise 'กวาดหน้าตัดไม่สำเร็จ — หน้าตัดควรตั้งฉากกับแนวที่ปลายเส้น'
          loose = ents.grep(Sketchup::Edge).select { |e| e.faces.empty? }
          ents.erase_entities(loose) unless loose.empty?
          g.name = r[0]
          g.material = RoadWay.material(r[1])
          g.layer = RoadWay.tag(r[2]) if RoadWay.tag(r[2])
          len = Sweep.length_m(path[:points])
          area = face.area.to_f * 0.0254**2
          RoadWay.stamp(g, kind: 'profile', label: r[0], profile: 'custom',
                           length_m: len, section_m2: area, volume_m3: area * len)
          g
        end
      end

      def array_along
        sel = Sketchup.active_model.selection
        inst = sel.grep(Sketchup::ComponentInstance).first
        unless inst
          UI.messagebox('เลือก Component 1 ชิ้น (คลิกขวา ▸ Make Component) พร้อมเส้นแนว')
          return
        end
        path = Sweep.ordered_path(sel.grep(Sketchup::Edge))
        unless path
          UI.messagebox('เลือกเส้นแนวต่อเนื่องเส้นเดียวพร้อม Component')
          return
        end
        r = RoadWay.ask(:pb_array, ['ระยะห่าง (ม.)', 'เริ่มที่ระยะ (ม.)', 'วางที่ปลายแนวด้วย', 'หมุนตามแนว'],
                        ['2.0', '0', 'ใช่', 'ใช่'], ['', '', 'ใช่|ไม่', 'ใช่|ไม่'],
                        'RoadWay — ชิ้นส่วนเรียงตามแนว') or return
        spacing = r[0].to_f
        if spacing <= 0
          UI.messagebox('ระยะห่างต้องมากกว่า 0')
          return
        end
        sts = Geo.stations(path[:points].map(&:to_a), spacing.m.to_f, r[1].to_f.m.to_f, r[2] == 'ใช่')
        if sts.size > 2000
          return unless UI.messagebox("จะวาง #{sts.size} ชิ้น ดำเนินการต่อ?", MB_YESNO) == IDYES
        end
        RoadWay.operation('RoadWay: ชิ้นส่วนเรียงตามแนว') do
          ents = Sketchup.active_model.active_entities
          t0 = inst.transformation
          base = Geom::Transformation.translation(t0.origin).inverse * t0
          a0 = Math.atan2(sts[0][1][1], sts[0][1][0])
          sts.each_with_index do |(pt, dir), i|
            rot = Geom::Transformation.new
            if r[3] == 'ใช่' && (dir[0].abs + dir[1].abs) > 1e-9
              rot = Geom::Transformation.rotation(ORIGIN, Z_AXIS, Math.atan2(dir[1], dir[0]) - a0)
            end
            t = Geom::Transformation.translation(Geom::Point3d.new(*pt)) * rot * base
            c = ents.add_instance(inst.definition, t)
            c.layer = inst.layer
            c.material = inst.material
            RoadWay.stamp(c, kind: 'assembly', label: inst.definition.name, station: i + 1)
          end
        end
      end
    end
  end
end
