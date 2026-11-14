# RoadWay — ส่วนกลาง: เมนู แถบเครื่องมือ และฟังก์ชันใช้ร่วม
require 'sketchup.rb'
require 'json'

module WanicnSurvey
  module RoadWay
    DICT = 'RoadWay'.freeze
    DIR  = File.dirname(__FILE__)

    %w[geo profiles rebar_calc sweep profile_builder road_builder rebar quantifier].each do |f|
      Sketchup.require(File.join(DIR, f))
    end

    module_function

    # ---------- ช่วยใช้ร่วม ----------

    def material(name, color = nil)
      return nil if name.nil? || name.strip.empty? || name == '(ไม่กำหนด)'
      mats = Sketchup.active_model.materials
      mats[name] || begin
        m = mats.add(name)
        m.color = color || Sketchup::Color.new(200, 200, 200)
        m
      end
    end

    def tag(name)
      return nil if name.nil? || name.strip.empty?
      Sketchup.active_model.layers.add(name)
    end

    def tag_names
      Sketchup.active_model.layers.map(&:name)
    end

    def material_names
      ['(ไม่กำหนด)'] + Sketchup.active_model.materials.map(&:name)
    end

    # บันทึกข้อมูลลงวัตถุ (ใช้ในรายงานถอดปริมาณ)
    def stamp(ent, data)
      data.each { |k, v| ent.set_attribute(DICT, k.to_s, v) }
      ent
    end

    def info(ent)
      d = ent.attribute_dictionary(DICT)
      d ? d.to_h : nil
    end

    # inputbox ที่จำค่าล่าสุด และคืน nil ถ้ากดยกเลิก
    @memory = {}
    def ask(key, prompts, defaults, lists = nil, title = PLUGIN_NAME)
      vals = @memory[key] || defaults
      vals = defaults if vals.size != defaults.size
      res = lists ? UI.inputbox(prompts, vals, lists, title) : UI.inputbox(prompts, vals, title)
      return nil unless res
      @memory[key] = res
      res
    end

    def selected_path
      sel = Sketchup.active_model.selection
      path = Sweep.ordered_path(sel.to_a)
      unless path
        UI.messagebox("เลือกเส้น (Edge/Arc) เป็นแนวต่อเนื่องเส้นเดียวก่อน\n" \
                      'แนวต้องไม่แตกแขนง และเส้นต้องอยู่ในบริบทเดียวกัน (ไม่อยู่คนละกลุ่ม)')
      end
      path
    end

    # ห่อคำสั่งเป็น 1 ขั้น Undo และแสดงข้อผิดพลาดเป็นภาษาไทย
    def operation(name)
      model = Sketchup.active_model
      model.start_operation(name, true)
      result = yield
      model.commit_operation
      result
    rescue StandardError => e
      model.abort_operation
      UI.messagebox("#{name}: #{e.message}")
      puts "[RoadWay] #{e.class}: #{e.message}\n#{e.backtrace.first(5).join("\n")}"
      nil
    end

    # ---------- เมนูและแถบเครื่องมือ ----------

    def cmd(text, tip, icon, &block)
      c = UI::Command.new(text, &block)
      c.tooltip = text
      c.status_bar_text = tip
      small = File.join(DIR, 'icons', "#{icon}_16.png")
      large = File.join(DIR, 'icons', "#{icon}_24.png")
      c.small_icon = small if File.exist?(small)
      c.large_icon = large if File.exist?(large)
      c
    end

    def setup_ui
      cmds = [
        cmd('โปรไฟล์ตามแนว', 'เลือกแนวเส้น แล้วกวาดหน้าตัดไปตามแนว (คาน ท่อ เหล็กรูปพรรณ คันหิน ราง)', 'profile') { ProfileBuilder.run },
        cmd('โปรไฟล์จากหน้าที่เลือก', 'เลือกหน้า (Face) 1 หน้า + แนวเส้น แล้วกวาดหน้านั้นตามแนว', 'profile_face') { ProfileBuilder.from_face },
        cmd('ชิ้นส่วนเรียงตามแนว', 'เลือก Component 1 ชิ้น + แนวเส้น แล้ววางซ้ำตามระยะ (เสา ไฟถนน หลักกิโล)', 'assembly') { ProfileBuilder.array_along },
        nil,
        cmd('ถนนตามแนว', 'เลือกแนวศูนย์กลางถนน แล้วสร้างผิวทางและชั้นโครงสร้างทาง', 'road') { RoadBuilder.run },
        nil,
        cmd('เหล็กเสริมคาน', 'สร้างคาน คสล. พร้อมเหล็กบน เหล็กล่าง และเหล็กปลอก', 'rebar_beam') { Rebar.beam },
        cmd('เหล็กเสริมเสา', 'สร้างเสา คสล. พร้อมเหล็กยืนและเหล็กปลอก', 'rebar_column') { Rebar.column },
        cmd('เหล็กเสริมพื้น/ฐานราก', 'สร้างแผ่นพื้นหรือฐานแผ่ พร้อมตะแกรงเหล็ก 2 ทาง', 'rebar_slab') { Rebar.slab },
        cmd('เหล็กตามแนว', 'เลือกแนวเส้น แล้วสร้างเหล็กเส้นดัดตามรูปแนว', 'rebar_path') { Rebar.along_path },
        nil,
        cmd('ถอดปริมาณและราคา', 'รายงานความยาว พื้นที่ ปริมาตร น้ำหนัก ราคา และตารางตัดเหล็ก', 'quantity') { Quantifier.show },
        cmd('ตรวจวัตถุที่เลือก', 'ดูข้อมูล RoadWay ของวัตถุที่เลือก', 'inspect') { Quantifier.inspect_selection }
      ]
      menu = UI.menu('Extensions').add_submenu(PLUGIN_NAME)
      tb = UI::Toolbar.new(PLUGIN_NAME)
      cmds.each do |c|
        if c
          menu.add_item(c)
          tb.add_item(c)
        else
          menu.add_separator
          tb.add_separator
        end
      end
      menu.add_separator
      menu.add_item("เกี่ยวกับ RoadWay #{VERSION}") do
        UI.messagebox("RoadWay #{VERSION}\nWANICNSURVEY — นายเวนิช ธัมมะวงษ์\n\n" \
                      "ปริมาณและราคาที่ได้เป็นค่าประมาณจากโมเดล\n" \
                      'ผู้มีหน้าที่ต้องตรวจสอบก่อนใช้งานจริง')
      end
      tb.get_last_state == TB_NEVER_SHOWN ? tb.show : tb.restore
    end

    unless file_loaded?(__FILE__)
      setup_ui
      file_loaded(__FILE__)
    end
  end
end
