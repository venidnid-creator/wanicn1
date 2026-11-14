# คลังหน้าตัดแบบพารามิเตอร์ (Ruby ล้วน, หน่วยเมตร)
# หน้าตัดคืนค่าเป็นรายการวง (loops): วงแรกคือขอบนอก วงถัดไปคือรู
# พิกัดท้องถิ่น: x = แนวขวาง, y = แนวตั้ง (ขึ้น)
module WanicnSurvey
  module RoadWay
    module Profiles
      module_function

      # ค่าตั้งต้นเป็นเพียงตัวอย่างให้กรอกแก้ ไม่ใช่ขนาดมาตรฐาน — ผู้ใช้ต้องใส่ขนาดจริงจากแบบ
      CATALOG = {
        'rect'    => { name: 'สี่เหลี่ยมตัน (ไม้/คาน)',      params: [['กว้าง', 0.10], ['สูง', 0.10]] },
        'circle'  => { name: 'กลมตัน',                       params: [['เส้นผ่านศูนย์กลาง', 0.10]] },
        'pipe'    => { name: 'ท่อกลม',                       params: [['เส้นผ่านศูนย์กลางนอก', 0.10], ['ความหนา', 0.005]] },
        'tube'    => { name: 'ท่อเหลี่ยม/กล่อง',              params: [['กว้าง', 0.10], ['สูง', 0.10], ['ความหนา', 0.003]] },
        'ibeam'   => { name: 'เหล็กรูปพรรณ I / H',            params: [['สูง', 0.20], ['ปีกกว้าง', 0.10], ['เอวหนา', 0.0055], ['ปีกหนา', 0.008]] },
        'channel' => { name: 'เหล็กรางน้ำ (C)',               params: [['สูง', 0.15], ['ปีกกว้าง', 0.075], ['เอวหนา', 0.0065], ['ปีกหนา', 0.010]] },
        'angle'   => { name: 'เหล็กฉาก (L)',                  params: [['ขาตั้ง', 0.05], ['ขานอน', 0.05], ['ความหนา', 0.005]] },
        'tee'     => { name: 'เหล็กรูปตัว T',                 params: [['สูง', 0.10], ['ปีกกว้าง', 0.10], ['เอวหนา', 0.006], ['ปีกหนา', 0.008]] },
        'kerb'    => { name: 'คันหิน (Kerb)',                 params: [['สูง', 0.30], ['กว้างบน', 0.15], ['กว้างล่าง', 0.20]] },
        'uditch'  => { name: 'รางระบายน้ำรูปตัว U',          params: [['กว้างใน', 0.40], ['ลึกใน', 0.50], ['ผนังหนา', 0.10]] }
      }.freeze

      ANCHORS = %w[กลาง บนซ้าย บนกลาง บนขวา กลางซ้าย กลางขวา ล่างซ้าย ล่างกลาง ล่างขวา].freeze

      def build(type, vals)
        v = vals.map(&:to_f)
        raise ArgumentError, 'ขนาดต้องมากกว่า 0' if v.any? { |x| x <= 0 }
        case type
        when 'rect'    then [rect(v[0], v[1])]
        when 'circle'  then [circle(v[0] / 2.0)]
        when 'pipe'
          raise ArgumentError, 'ท่อหนาเกินรัศมี' if v[1] * 2 >= v[0]
          [circle(v[0] / 2.0), circle(v[0] / 2.0 - v[1])]
        when 'tube'
          raise ArgumentError, 'ท่อหนาเกินขนาด' if v[2] * 2 >= [v[0], v[1]].min
          [rect(v[0], v[1]), rect(v[0] - 2 * v[2], v[1] - 2 * v[2])]
        when 'ibeam'   then [ibeam(*v[0, 4])]
        when 'channel' then [channel(*v[0, 4])]
        when 'angle'   then [angle(*v[0, 3])]
        when 'tee'     then [tee(*v[0, 4])]
        when 'kerb'    then [kerb(*v[0, 3])]
        when 'uditch'  then [uditch(*v[0, 3])]
        else raise ArgumentError, "ไม่รู้จักหน้าตัด #{type}"
        end
      end

      # สี่เหลี่ยมมีจุดศูนย์กลางที่ 0,0
      def rect(w, h)
        [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]
      end

      def circle(r, seg = 24)
        (0...seg).map do |i|
          a = 2 * Math::PI * i / seg
          [r * Math.cos(a), r * Math.sin(a)]
        end
      end

      def ibeam(h, b, tw, tf)
        x = b / 2; w = tw / 2; y = h / 2; yi = y - tf
        [[-x, -y], [x, -y], [x, -yi], [w, -yi], [w, yi], [x, yi], [x, y],
         [-x, y], [-x, yi], [-w, yi], [-w, -yi], [-x, -yi]]
      end

      def channel(h, b, tw, tf)
        y = h / 2; yi = y - tf
        [[0, -y], [b, -y], [b, -yi], [tw, -yi], [tw, yi], [b, yi], [b, y], [0, y]]
      end

      def angle(a, b, t)
        [[0, 0], [b, 0], [b, t], [t, t], [t, a], [0, a]]
      end

      def tee(h, b, tw, tf)
        x = b / 2; w = tw / 2
        [[-w, 0], [w, 0], [w, h - tf], [x, h - tf], [x, h], [-x, h], [-x, h - tf], [-w, h - tf]]
      end

      # คันหิน: หน้าเอียงด้านถนน (x ลบ)
      def kerb(h, wt, wb)
        [[0, 0], [wb, 0], [wb, h], [wb - wt, h]]
      end

      def uditch(wi, di, t)
        x = wi / 2
        [[-x - t, -t], [x + t, -t], [x + t, di], [x, di], [x, 0], [-x, 0], [-x, di], [-x - t, di]]
      end

      def bbox(loops)
        xs = loops.flatten(1).map { |p| p[0] }
        ys = loops.flatten(1).map { |p| p[1] }
        [xs.min, ys.min, xs.max, ys.max]
      end

      # จัดหน้าตัดให้จุดยึด (anchor) อยู่ที่ 0,0 แล้วเลื่อน/หมุน/กลับด้าน
      def place(loops, anchor = 'กลาง', dx = 0.0, dy = 0.0, rot_deg = 0.0, mirror = false)
        x0, y0, x1, y1 = bbox(loops)
        cx = case anchor
             when /ซ้าย/ then x0
             when /ขวา/  then x1
             else (x0 + x1) / 2.0
             end
        cy = case anchor
             when /\Aบน/  then y1
             when /\Aล่าง/ then y0
             else (y0 + y1) / 2.0
             end
        a = rot_deg.to_f * Math::PI / 180.0
        c = Math.cos(a); s = Math.sin(a)
        loops.map do |loop|
          pts = loop.map do |x, y|
            px = x - cx
            px = -px if mirror
            py = y - cy
            [px * c - py * s + dx, px * s + py * c + dy]
          end
          mirror ? pts.reverse : pts
        end
      end

      # พื้นที่หน้าตัด (ตร.ม.) = ขอบนอก − รู
      def area(loops)
        loops.each_with_index.inject(0.0) do |sum, (lp, i)|
          a = (0...lp.size).inject(0.0) do |s, k|
            p = lp[k]; q = lp[(k + 1) % lp.size]
            s + p[0] * q[1] - q[0] * p[1]
          end.abs / 2.0
          i.zero? ? sum + a : sum - a
        end
      end

      # หน้าตัดถนนครึ่งซีก 2 ข้าง (y = 0 คือระดับหลังถนนที่แนวศูนย์กลาง)
      # คืน { 'ผิวทาง' => loops, 'ชั้นพื้นทาง' => loops, ... }
      def road_section(o)
        lane  = o[:lane_w] * o[:lanes]   # ความกว้างผิวจราจรต่อข้าง
        sh    = o[:shoulder_w]
        cross = o[:crown_pct] / 100.0
        shs   = o[:shoulder_pct] / 100.0
        # จุดผิวบนจากซ้ายไปขวา
        top = lambda do |x|
          ax = x.abs
          ax <= lane ? -ax * cross : -lane * cross - (ax - lane) * shs
        end
        xs = [-(lane + sh), -lane, 0.0, lane, lane + sh].uniq.sort
        layers = {}
        depth = 0.0
        o[:layers].each do |name, thick|
          next if thick <= 0
          upper = xs.map { |x| [x, top.call(x) - depth] }
          lower = xs.map { |x| [x, top.call(x) - depth - thick] }
          layers[name] = [lower + upper.reverse] # ล่างซ้าย→ขวา แล้วบนขวา→ซ้าย
          depth += thick
        end
        layers
      end
    end
  end
end
