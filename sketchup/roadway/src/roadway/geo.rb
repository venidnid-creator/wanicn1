# เรขาคณิตแบบ Ruby ล้วน (ไม่พึ่ง SketchUp API) — ทดสอบนอก SketchUp ได้
# จุดเป็น [x, y, z] ใช้หน่วยใดก็ได้ ขอให้สม่ำเสมอ
module WanicnSurvey
  module RoadWay
    module Geo
      module_function

      def sub(a, b)  [a[0] - b[0], a[1] - b[1], a[2] - b[2]] end
      def add(a, b)  [a[0] + b[0], a[1] + b[1], a[2] + b[2]] end
      def mul(a, s)  [a[0] * s, a[1] * s, a[2] * s] end
      def len(a)     Math.sqrt(a[0]**2 + a[1]**2 + a[2]**2) end

      def unit(a)
        l = len(a)
        l < 1e-12 ? [0.0, 0.0, 0.0] : mul(a, 1.0 / l)
      end

      # ตัดจุดซ้ำติดกัน
      def dedupe(pts, tol = 1e-6)
        pts.each_with_object([]) do |p, out|
          out << p if out.empty? || len(sub(p, out[-1])) > tol
        end
      end

      def polyline_length(pts)
        (1...pts.size).inject(0.0) { |s, i| s + len(sub(pts[i], pts[i - 1])) }
      end

      # จุดวางตามแนว: ทุก spacing เริ่มที่ระยะ start
      # คืน [[จุด, ทิศทาง(unit)], ...]
      def stations(pts, spacing, start = 0.0, include_end = false)
        pts = dedupe(pts)
        return [] if pts.size < 2 || spacing <= 0
        total = polyline_length(pts)
        out = []
        d = start.to_f
        while d <= total + 1e-9
          out << point_at(pts, d)
          d += spacing
        end
        if include_end && (out.empty? || total - (d - spacing) > spacing * 0.01)
          out << point_at(pts, total)
        end
        out
      end

      # จุดและทิศทางที่ระยะ d ตามแนว
      def point_at(pts, d)
        acc = 0.0
        (1...pts.size).each do |i|
          seg = sub(pts[i], pts[i - 1])
          l = len(seg)
          next if l < 1e-12
          if acc + l >= d - 1e-9 || i == pts.size - 1
            t = [[(d - acc) / l, 0.0].max, 1.0].min
            return [add(pts[i - 1], mul(seg, t)), unit(seg)]
          end
          acc += l
        end
        [pts[-1], unit(sub(pts[-1], pts[-2]))]
      end

    end
  end
end
