# การคำนวณเหล็กเสริม (Ruby ล้วน, หน่วยเมตร) — ทดสอบนอก SketchUp ได้
# ใช้หลักเดียวกับ WANICNSURVEY 3D (core/wanic_rc.py):
#   น้ำหนัก 0.00617 d² กก./ม. · ทาบ 40d (DB) / 48d (RB) ไม่น้อยกว่า 0.30 ม.
#   ขอ 12d · ขอเหล็กปลอก 135° รวม 0.10 ม. x 2 · เศษ 5 % · ลวดผูก 20 กก./ตัน
module WanicnSurvey
  module RoadWay
    module RebarCalc
      module_function

      SIZES = { 'RB' => [6, 9, 12, 15, 19, 25], 'DB' => [10, 12, 16, 20, 25, 28, 32] }.freeze
      GRADE = { 'RB' => 'SR24', 'DB' => 'SD40' }.freeze
      COVER = { 'footing' => 0.075, 'stump' => 0.040, 'column' => 0.035,
                'beam' => 0.030, 'slab' => 0.020 }.freeze
      WASTE = 0.05
      TIE_WIRE_KG_PER_T = 20.0
      STIRRUP_HOOK = 0.10
      BAR_RE = /\A\s*(?:(\d+)\s*[-×x]\s*)?(RB|DB|SR|SD)\s*(\d+)\s*(?:@\s*([\d.]+))?\s*\z/i

      # "4-DB12" → {kind:'DB', d:12, n:4, s:0.0} · "RB6@0.15" → {kind:'RB', d:6, n:0, s:0.15}
      def parse(text)
        m = BAR_RE.match(text.to_s.delete('Øø'))
        return nil unless m
        kind = m[2].upcase
        kind = { 'SR' => 'RB', 'SD' => 'DB' }.fetch(kind, kind)
        { kind: kind, d: m[3].to_i, n: m[1].to_i, s: m[4].to_f, text: "#{kind}#{m[3]}" }
      end

      def parse!(text, need)
        b = parse(text)
        raise ArgumentError, "รูปแบบเหล็กไม่ถูกต้อง: «#{text}» (ตัวอย่าง 4-DB12, RB6@0.15)" unless b
        raise ArgumentError, "«#{text}» ต้องระบุจำนวน เช่น 4-#{b[:text]}" if need == :n && b[:n] <= 0
        raise ArgumentError, "«#{text}» ต้องระบุระยะ เช่น #{b[:text]}@0.15" if need == :s && b[:s] <= 0
        b
      end

      def kg_m(d)        0.00617 * d * d end
      def hook(b)        12 * b[:d] / 1000.0 end
      def lap(b)         [(b[:kind] == 'DB' ? 40 : 48) * b[:d] / 1000.0, 0.30].max end
      def dm(b)          b[:d] / 1000.0 end

      def path_len(pts)
        (1...pts.size).inject(0.0) do |s, i|
          a = pts[i - 1]; c = pts[i]
          s + Math.sqrt((c[0] - a[0])**2 + (c[1] - a[1])**2 + (c[2] - a[2])**2)
        end
      end

      # เหล็ก 1 เส้น: pts = แนวศูนย์กลาง (ม.) · length = ความยาวตัด (ม.)
      def bar(mark, b, pts, shape, extra = 0.0)
        { mark: mark, bar: b[:text], kind: b[:kind], d: b[:d], pts: pts, shape: shape,
          length: (path_len(pts) + extra).round(3) }
      end

      # ตำแหน่งเหล็ก n เส้นเรียงเท่ากันระหว่าง a..b
      def spread(n, a, b)
        return [(a + b) / 2.0] if n == 1
        (0...n).map { |i| a + (b - a) * i / (n - 1).to_f }
      end

      # ---------- คาน: x ตามแนวคาน 0..L, y ขวาง, z = 0 ที่หลังคาน (ลงเป็นลบ) ----------
      def beam(o)
        b = o[:b].to_f; h = o[:h].to_f; len = o[:L].to_f
        c = (o[:cover] || COVER['beam']).to_f
        top = parse!(o[:top], :n); bot = parse!(o[:bot], :n); st = parse!(o[:stirrup], :s)
        check_dims!(b, h, len)
        mk = o[:mark] || 'B1'
        bars = []
        [[top, -(c + dm(st) + dm(top) / 2), -1, 'T'], [bot, -h + c + dm(st) + dm(bot) / 2, 1, 'B']].each do |bb, z, hk, tag|
          w = b / 2 - c - dm(st) - dm(bb) / 2
          raise ArgumentError, 'คานแคบเกินไปสำหรับเหล็กที่กำหนด' if w <= 0
          spread(bb[:n], -w, w).each do |y|
            hz = z + hk * hook(bb)
            pts = [[c, y, hz], [c, y, z], [len - c, y, z], [len - c, y, hz]]
            bars << bar("#{mk}-#{tag}", bb, pts, 'งอฉาก 2 ปลาย')
          end
        end
        bars.concat(stirrups(mk, st, len, b, h, c, :beam))
        { mark: mk, kind: 'beam', concrete_m3: b * h * len, form_m2: (b + 2 * h) * len, bars: bars }
      end

      # ปลอกคาน (ระนาบ y-z) หรือปลอกเสา (ระนาบ x-y)
      def stirrups(mk, st, len, b, h, c, where)
        y = b / 2 - c - dm(st) / 2
        z = h / 2 - c - dm(st) / 2
        raise ArgumentError, 'หน้าตัดเล็กเกินระยะหุ้ม' if y <= 0 || z <= 0
        n = ((len - 2 * 0.05) / st[:s]).floor + 1
        (0...n).map do |i|
          t = 0.05 + i * st[:s]
          ring = if where == :beam
                   zc = -h / 2.0
                   [[t, -y, zc - z], [t, y, zc - z], [t, y, zc + z], [t, -y, zc + z], [t, -y, zc - z]]
                 else
                   [[-y, -z, t], [y, -z, t], [y, z, t], [-y, z, t], [-y, -z, t]]
                 end
          bar("#{mk}-S", st, ring, 'ปลอก', 2 * STIRRUP_HOOK)
        end
      end

      # ---------- เสา: หน้าตัด bx x by ศูนย์กลาง 0,0 · z 0..H ----------
      def column(o)
        bx = o[:b].to_f; by = o[:h].to_f; hh = o[:H].to_f
        c = (o[:cover] || COVER['column']).to_f
        main = parse!(o[:main], :n); tie = parse!(o[:tie], :s)
        check_dims!(bx, by, hh)
        mk = o[:mark] || 'C1'
        x = bx / 2 - c - dm(tie) - dm(main) / 2
        y = by / 2 - c - dm(tie) - dm(main) / 2
        raise ArgumentError, 'เสาเล็กเกินไปสำหรับเหล็กที่กำหนด' if x <= 0 || y <= 0
        lp = o[:with_lap] == false ? 0.0 : lap(main)
        bars = column_positions([main[:n], 4].max, x, y).map do |px, py|
          bar("#{mk}-M", main, [[px, py, 0.0], [px, py, hh + lp]], 'ตรง (รวมระยะทาบ)')
        end
        bars.concat(stirrups(mk, tie, hh, bx, by, c, :column))
        { mark: mk, kind: 'column', concrete_m3: bx * by * hh, form_m2: 2 * (bx + by) * hh, bars: bars }
      end

      # มุม 4 เส้น แล้วเฉลี่ยที่เหลือลงด้านตามสัดส่วนความยาวด้าน
      def column_positions(n, x, y)
        pts = [[-x, -y], [x, -y], [x, y], [-x, y]]
        extra = n - 4
        kx = (extra * x / (x + y) / 2.0).floor
        ky = (extra - 2 * kx) / 2
        left = extra - 2 * kx - 2 * ky
        side = lambda do |k, a, b, fixed, along_x|
          (1..k).map do |i|
            v = a + (b - a) * i / (k + 1).to_f
            along_x ? [v, fixed] : [fixed, v]
          end
        end
        pts += side.call(kx + left, -x, x, -y, true)
        pts += side.call(kx, -x, x, y, true)
        pts += side.call(ky, -y, y, -x, false)
        pts += side.call(ky, -y, y, x, false)
        pts
      end

      # ---------- พื้น / ฐานราก: มุมที่ 0,0 · z 0..t ----------
      def slab(o)
        lx = o[:Lx].to_f; ly = o[:Ly].to_f; t = o[:t].to_f
        c = (o[:cover] || COVER['slab']).to_f
        bxx = parse!(o[:bars_x], :s); byy = parse!(o[:bars_y], :s)
        check_dims!(lx, ly, t)
        mk = o[:mark] || 'S1'
        layers = [['B', c, 1]]
        layers << ['T', t - c, -1] if o[:top]
        bars = []
        layers.each do |tag, zface, dir|
          zx = zface + dir * dm(bxx) / 2
          zy = zx + dir * (dm(bxx) / 2 + dm(byy) / 2)
          hx = dir * hook(bxx); hy = dir * hook(byy)
          spread(count(ly, c, bxx[:s]), c, ly - c).each do |y|
            bars << bar("#{mk}-#{tag}X", bxx, [[c, y, zx + hx], [c, y, zx], [lx - c, y, zx], [lx - c, y, zx + hx]], 'งอฉาก 2 ปลาย')
          end
          spread(count(lx, c, byy[:s]), c, lx - c).each do |x|
            bars << bar("#{mk}-#{tag}Y", byy, [[x, c, zy + hy], [x, c, zy], [x, ly - c, zy], [x, ly - c, zy + hy]], 'งอฉาก 2 ปลาย')
          end
        end
        { mark: mk, kind: o[:footing] ? 'footing' : 'slab', concrete_m3: lx * ly * t,
          form_m2: o[:footing] ? 2 * (lx + ly) * t : lx * ly, bars: bars }
      end

      def count(len, c, s)
        [((len - 2 * c) / s).floor + 1, 2].max
      end

      def check_dims!(*v)
        raise ArgumentError, 'ขนาดต้องมากกว่า 0' if v.any? { |x| x <= 0 }
      end

      # ---------- ตารางตัดเหล็ก ----------
      # items: [{mark, bar, kind, d, length, shape, count}]
      def cut_list(items)
        rows = Hash.new { |hh, k| hh[k] = { count: 0 } }
        items.each do |it|
          key = [it[:mark], it[:bar], it[:length].to_f.round(2), it[:shape]]
          r = rows[key]
          r.merge!(mark: it[:mark], bar: it[:bar], kind: it[:kind], d: it[:d],
                   length: key[2], shape: it[:shape])
          r[:count] += (it[:count] || 1).to_i
        end
        list = rows.values.sort_by { |r| [r[:mark].to_s, r[:d], -r[:length]] }
        list.each do |r|
          r[:total_m] = (r[:length] * r[:count]).round(2)
          r[:kg] = (r[:total_m] * kg_m(r[:d])).round(2)
        end
        list
      end

      # สรุปตามขนาดเหล็ก + เศษ + ลวดผูก
      def summary(list)
        by = Hash.new { |hh, k| hh[k] = { total_m: 0.0, kg: 0.0 } }
        list.each do |r|
          s = by[r[:bar]]
          s[:kind] = r[:kind]; s[:d] = r[:d]
          s[:total_m] += r[:total_m]; s[:kg] += r[:kg]
        end
        rows = by.map do |b, s|
          { bar: b, grade: GRADE[s[:kind]], total_m: s[:total_m].round(2), kg: s[:kg].round(2),
            kg_waste: (s[:kg] * (1 + WASTE)).round(2) }
        end.sort_by { |r| [r[:bar][0, 2], r[:bar][2..-1].to_i] }
        total = rows.inject(0.0) { |a, r| a + r[:kg_waste] }
        { rows: rows, kg: total.round(2), tie_wire_kg: (total / 1000.0 * TIE_WIRE_KG_PER_T).round(2) }
      end
    end
  end
end
