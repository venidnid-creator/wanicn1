# 2) ถอดปริมาณและราคา (แทน Quantifier Pro) + ตารางตัดเหล็ก
module WanicnSurvey
  module RoadWay
    Sketchup.require(File.join(File.dirname(__FILE__), 'report'))

    module Quantifier
      module_function

      RULES_DICT = 'RoadWay_Cost'.freeze
      IN3_TO_M3 = 0.0254**3
      IN2_TO_M2 = 0.0254**2

      # ---------- เก็บรายการจากโมเดล ----------

      def items
        out = []
        model = Sketchup.active_model
        walk(model.entities, Geom::Transformation.new, out)
        out
      end

      def walk(ents, tr, out)
        ents.each do |e|
          next unless e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)
          next unless e.visible? && e.layer.visible?
          t = tr * e.transformation
          i = RoadWay.info(e)
          kind = i && i['kind']
          if %w[rebar concrete profile road assembly].include?(kind)
            out << from_roadway(e, i)
          elsif kind == 'element' || children?(e)
            walk(entities_of(e), t, out)
          else
            out << generic(e, t)
          end
        end
      end

      def entities_of(e)
        e.is_a?(Sketchup::Group) ? e.entities : e.definition.entities
      end

      def children?(e)
        entities_of(e).any? { |x| x.is_a?(Sketchup::Group) || x.is_a?(Sketchup::ComponentInstance) }
      end

      def name_of(e)
        return e.name unless e.name.to_s.empty?
        e.is_a?(Sketchup::ComponentInstance) ? e.definition.name : 'กลุ่มไม่มีชื่อ'
      end

      def mat_of(e)
        e.material ? e.material.display_name : '(ไม่กำหนด)'
      end

      def from_roadway(e, i)
        base = { label: name_of(e), material: mat_of(e), tag: e.layer.name, kind: i['kind'],
                 count: 1, length: 0.0, area: 0.0, volume: 0.0, kg: 0.0 }
        case i['kind']
        when 'rebar'
          n = (i['count'] || 1).to_i
          base.merge(label: "เหล็ก #{i['bar']}", count: n, length: i['length_m'].to_f * n,
                     kg: i['kg'].to_f, mark: i['mark'], bar: i['bar'], bar_kind: i['bar_kind'],
                     d: i['dia_mm'].to_i, cut: i['length_m'].to_f, shape: i['shape'])
        when 'concrete'
          base.merge(label: "คอนกรีต#{Rebar.label(i['element'])}", volume: i['volume_m3'].to_f,
                     area: i['form_m2'].to_f)
        when 'profile', 'road'
          base.merge(label: i['label'] || name_of(e), length: i['length_m'].to_f,
                     area: i['area_m2'].to_f, volume: i['volume_m3'].to_f)
        else # assembly: นับเป็นชิ้น
          generic(e, e.transformation).merge(label: name_of(e), kind: 'assembly')
        end
      end

      def generic(e, t)
        vol = e.respond_to?(:volume) ? e.volume.to_f : -1
        area = entities_of(e).grep(Sketchup::Face).inject(0.0) { |s, f| s + f.area(t) }
        { label: name_of(e), material: mat_of(e), tag: e.layer.name, kind: 'object', count: 1,
          length: 0.0, area: area * IN2_TO_M2, volume: vol > 0 ? vol * IN3_TO_M3 : 0.0, kg: 0.0 }
      end

      # ---------- กฎราคา (เก็บในไฟล์ .skp) ----------

      def rules
        JSON.parse(Sketchup.active_model.get_attribute(RULES_DICT, 'rules', '[]'))
      rescue JSON::ParserError
        []
      end

      def save_rules(json)
        list = JSON.parse(json).select { |r| !r['key'].to_s.strip.empty? }
        model = Sketchup.active_model
        model.start_operation('RoadWay: บันทึกราคา', true)
        model.set_attribute(RULES_DICT, 'rules', JSON.generate(list))
        model.commit_operation
      end

      # ---------- ข้อมูลรายงาน ----------

      def data
        its = items
        rl = rules
        tabs = {}
        Report::BY.each do |by|
          rows = Report.group(its, by.to_sym, rl)
          tabs[by] = { rows: rows, total: Report.totals(rows) }
        end
        bars = its.select { |x| x[:kind] == 'rebar' }.map do |x|
          { mark: x[:mark], bar: x[:bar], kind: x[:bar_kind], d: x[:d], length: x[:cut],
            shape: x[:shape], count: x[:count] }
        end
        cut = RebarCalc.cut_list(bars)
        keys = Report::BY.map { |by| [by, its.map { |x| x[by.to_sym].to_s }.uniq.sort] }.to_h
        { tabs: tabs, cut: cut, cutsum: RebarCalc.summary(cut), rules: rl, keys: keys,
          units: Report::UNIT_TH, model: Sketchup.active_model.title.to_s, version: VERSION,
          date: Time.now.strftime('%d/%m/') + (Time.now.year + 543).to_s }
      end

      # ---------- หน้าต่าง ----------

      def show
        if @dlg && @dlg.visible?
          @dlg.bring_to_front
          refresh
          return
        end
        @dlg = UI::HtmlDialog.new(dialog_title: 'RoadWay — ถอดปริมาณและราคา', preferences_key: 'RoadWayQty',
                                  width: 980, height: 680, resizable: true, style: UI::HtmlDialog::STYLE_DIALOG)
        @dlg.set_file(File.join(File.dirname(__FILE__), 'quantifier.html'))
        @dlg.add_action_callback('ready') { |_c| refresh }
        @dlg.add_action_callback('refresh') { |_c| refresh }
        @dlg.add_action_callback('save_rules') do |_c, json|
          save_rules(json)
          refresh
        end
        @dlg.add_action_callback('export_csv') { |_c, tab| export_csv(tab) }
        @dlg.add_action_callback('select') { |_c, tab, name| select_rows(tab, name) }
        @dlg.show
      end

      def refresh
        return unless @dlg
        @dlg.execute_script("render(#{JSON.generate(data)})")
      rescue StandardError => e
        puts "[RoadWay] #{e.class}: #{e.message}"
      end

      def export_csv(tab)
        d = data
        if tab == 'cut'
          header = %w[รหัส เหล็ก รูปแบบ ยาวตัด(ม.) จำนวน(เส้น) ยาวรวม(ม.) น้ำหนัก(กก.)]
          rows = d[:cut].map { |r| [r[:mark], r[:bar], r[:shape], r[:length], r[:count], r[:total_m], r[:kg]] }
          rows << []
          d[:cutsum][:rows].each { |r| rows << ['รวม', r[:bar], r[:grade], '', '', r[:total_m], r[:kg]] }
          rows << ['รวมเผื่อเศษ 5 %', '', '', '', '', '', d[:cutsum][:kg]]
          rows << ['ลวดผูกเหล็ก', '', '', '', '', '', d[:cutsum][:tie_wire_kg]]
        else
          t = d[:tabs][tab] or return
          header = %w[รายการ จำนวน ยาว(ม.) พื้นที่(ตร.ม.) ปริมาตร(ลบ.ม.) น้ำหนัก(กก.) ราคา(บาท)]
          rows = (t[:rows] + [t[:total]]).map do |r|
            [r[:name], r[:count], r[:length], r[:area], r[:volume], r[:kg], r[:cost]]
          end
        end
        rows << []
        rows << ['เครื่องมือช่วยคำนวณ — ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจและลงนามก่อนก่อสร้าง']
        rows << ['ผู้พัฒนา นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ', "RoadWay #{VERSION}", d[:date]]
        path = UI.savepanel('บันทึกตาราง (CSV)', '', "RoadWay-#{tab}.csv")
        return unless path
        path += '.csv' unless path =~ /\.csv\z/i
        File.open(path, 'wb') { |f| f.write(Report.csv(header, rows)) }
        UI.messagebox("บันทึกแล้ว:\n#{path}")
      end

      # คลิกแถวในรายงาน → เลือกวัตถุนั้นในโมเดล (ระดับบนสุด)
      def select_rows(tab, name)
        model = Sketchup.active_model
        model.selection.clear
        model.active_entities.each do |e|
          next unless e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)
          hit = []
          walk([e], Geom::Transformation.new, hit)
          model.selection.add(e) if hit.any? { |x| x[tab.to_sym].to_s == name }
        end
      end

      def inspect_selection
        e = Sketchup.active_model.selection.first
        i = e && RoadWay.info(e)
        unless i
          UI.messagebox('วัตถุที่เลือกไม่มีข้อมูล RoadWay')
          return
        end
        UI.messagebox(i.map { |k, v| "#{k}: #{v}" }.join("\n"))
      end
    end
  end
end
