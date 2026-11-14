# รวมปริมาณและคิดราคา (Ruby ล้วน) — ทดสอบนอก SketchUp ได้
# รายการ (item): { label:, material:, tag:, kind:, count:, length:, area:, volume:, kg: }
module WanicnSurvey
  module RoadWay
    module Report
      module_function

      QTY = %i[count length area volume kg].freeze
      UNITS = { 'ea' => :count, 'm' => :length, 'm2' => :area, 'm3' => :volume, 'kg' => :kg }.freeze
      UNIT_TH = { 'ea' => 'ชิ้น', 'm' => 'ม.', 'm2' => 'ตร.ม.', 'm3' => 'ลบ.ม.', 'kg' => 'กก.' }.freeze
      BY = %w[label material tag].freeze

      # กฎราคา: { 'by' => 'label|material|tag', 'key' =>, 'unit' => 'm3', 'price' =>, 'waste' => % }
      # ค้นกฎตามลำดับ ชื่อชิ้นส่วน → วัสดุ → Tag (ไม่มีราคาตั้งต้น ผู้ใช้กรอกเอง)
      def rule_for(item, rules)
        BY.each do |by|
          r = rules.find { |x| x['by'] == by && x['key'].to_s == item[by.to_sym].to_s }
          return r if r
        end
        nil
      end

      def cost(item, rules)
        r = rule_for(item, rules)
        return 0.0 unless r
        qty = item[UNITS.fetch(r['unit'], :count)].to_f
        (qty * (1 + r['waste'].to_f / 100.0) * r['price'].to_f).round(2)
      end

      def group(items, field, rules = [])
        rows = {}
        items.each do |it|
          key = it[field].to_s.empty? ? '(ไม่กำหนด)' : it[field].to_s
          r = rows[key] ||= { name: key, count: 0, length: 0.0, area: 0.0, volume: 0.0, kg: 0.0, cost: 0.0 }
          QTY.each { |q| r[q] += it[q].to_f }
          r[:cost] += cost(it, rules)
        end
        rows.values.sort_by { |r| r[:name] }.map do |r|
          r.merge(count: r[:count].round, length: r[:length].round(3), area: r[:area].round(3),
                  volume: r[:volume].round(4), kg: r[:kg].round(2), cost: r[:cost].round(2))
        end
      end

      def totals(rows)
        t = { name: 'รวม', count: 0, length: 0.0, area: 0.0, volume: 0.0, kg: 0.0, cost: 0.0 }
        rows.each { |r| (QTY + [:cost]).each { |q| t[q] += r[q].to_f } }
        t.merge(length: t[:length].round(3), area: t[:area].round(3), volume: t[:volume].round(4),
                kg: t[:kg].round(2), cost: t[:cost].round(2))
      end

      # CSV ที่โปรแกรมตารางคำนวณเปิดภาษาไทยได้ (UTF-8 มี BOM)
      def csv(header, rows)
        esc = lambda do |v|
          s = v.to_s
          s =~ /[",\n]/ ? "\"#{s.gsub('"', '""')}\"" : s
        end
        "﻿" + ([header] + rows).map { |r| r.map { |v| esc.call(v) }.join(',') }.join("\r\n") + "\r\n"
      end
    end
  end
end
