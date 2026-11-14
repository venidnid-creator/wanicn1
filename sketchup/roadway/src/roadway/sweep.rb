# ตัวกวาดหน้าตัดตามแนว (ใช้ร่วมกันทั้งโปรไฟล์ ถนน และเหล็กเสริม)
module WanicnSurvey
  module RoadWay
    module Sweep
      module_function

      # เรียงเส้นที่เลือกให้เป็นแนวต่อเนื่อง
      # คืน { points: [Point3d], closed: bool } หรือ nil (ถ้าแตกแขนง/ไม่ต่อกัน)
      def ordered_path(entities)
        edges = entities.grep(Sketchup::Edge)
        return nil if edges.empty?
        count = Hash.new(0)
        edges.each { |e| e.vertices.each { |v| count[v] += 1 } }
        return nil if count.values.any? { |c| c > 2 }
        closed = count.values.all? { |c| c == 2 }
        start = count.keys.find { |v| count[v] == 1 } || edges.first.start
        remaining = edges.dup
        cur = start
        pts = [cur.position]
        until remaining.empty?
          e = remaining.find { |ed| ed.used_by?(cur) }
          return nil unless e
          remaining.delete(e)
          cur = e.other_vertex(cur)
          pts << cur.position
        end
        { points: pts, closed: closed }
      end

      # แกนของหน้าตัด: z = ทิศแนว, y = ใกล้แนวดิ่งมากที่สุด
      def section_transform(origin, dir)
        dir = dir.normalize
        up = Z_AXIS
        up = Y_AXIS if dir.parallel?(Z_AXIS)
        xaxis = up.cross(dir).normalize
        yaxis = dir.cross(xaxis).normalize
        Geom::Transformation.axes(origin, xaxis, yaxis, dir)
      end

      def to_pts(arr)
        arr.map { |p| p.is_a?(Geom::Point3d) ? p : Geom::Point3d.new(*p) }
      end

      # กวาดหน้าตัด loops (เมตร) ไปตามจุด path_pts (Point3d, หน่วยภายใน)
      # คืน Group ใหม่ใน entities
      def sweep(entities, loops, path_pts, name = nil, material = nil)
        pts = to_pts(Geo.dedupe(path_pts.map(&:to_a)))
        raise ArgumentError, 'แนวต้องมีอย่างน้อย 2 จุด' if pts.size < 2
        closed = pts.size > 3 && pts.first.distance(pts.last) < 0.001
        if closed
          # เริ่มกลางช่วงแรก กันรอยต่อที่มุม
          mid = Geom.linear_combination(0.5, pts[0], 0.5, pts[1])
          pts = [mid] + pts[1..-2] + [pts[0], mid]
        end
        group = entities.add_group
        ents = group.entities
        tr = section_transform(pts[0], pts[0].vector_to(pts[1]))
        conv = ->(lp) { lp.map { |x, y| Geom::Point3d.new(x.to_f.m, y.to_f.m, 0).transform(tr) } }
        ents.add_face(conv.call(loops[0]))
        loops[1..-1].each do |hole|
          hf = ents.add_face(conv.call(hole))
          hf.erase! if hf && hf.valid?
        end
        face = ents.grep(Sketchup::Face).first
        raise 'สร้างหน้าตัดไม่สำเร็จ (ขนาดเล็กเกินไป?)' unless face
        path = ents.add_curve(pts)
        ok = face.followme(path)
        loose = ents.grep(Sketchup::Edge).select { |e| e.faces.empty? }
        ents.erase_entities(loose) unless loose.empty?
        unless ok && ents.grep(Sketchup::Face).size > 1
          group.erase!
          raise 'กวาดหน้าตัดไม่สำเร็จ ลองตรวจแนวว่ามีมุมแคบหรือเส้นซ้อนกันหรือไม่'
        end
        group.name = name if name
        group.material = material if material
        group
      end

      # ความยาวแนว (เมตร)
      def length_m(path_pts)
        Geo.polyline_length(path_pts.map(&:to_a)).to_l.to_m
      end
    end
  end
end
