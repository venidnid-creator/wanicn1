# สร้างข้อมูลรายงานจากโมเดลตัวอย่าง (คาน เสา พื้น ถนน + ราคาตัวอย่างสำหรับภาพหน้าจอ) → JSON
require_relative 'sketchup_stub'
$LOADED_FEATURES << 'sketchup.rb' << 'extensions.rb'
module WanicnSurvey; module RoadWay; VERSION = '1.0.0'; PLUGIN_NAME = 'RoadWay'; end; end
require_relative '../src/roadway/core'
RW = WanicnSurvey::RoadWay
m = Sketchup.active_model
click = lambda do |pt|
  m.tool.instance_variable_get(:@ip).position = pt
  m.tool.onLButtonDown(0, 0, 0, nil)
end
UI.answers = [:default]; RW::Rebar.beam; click.call(ORIGIN)
UI.answers = [['B2', '0.25', '0.50', '6.00', '0.03', '3-DB16', '3-DB16', 'RB9@0.15', 'ท่อ 3 มิติ']]
RW::Rebar.beam; click.call(ORIGIN)
UI.answers = [:default]; RW::Rebar.column; click.call(ORIGIN)
UI.answers = [:default]; RW::Rebar.slab; click.call(ORIGIN)
UI.answers = [['F1', 'ฐานราก', '1.20', '1.20', '0.30', '0.075', 'DB12@0.15', 'DB12@0.15', 'ไม่', 'ท่อ 3 มิติ']]
RW::Rebar.slab; click.call(ORIGIN)
e = m.entities.add_curve([ORIGIN, Geom::Point3d.new(250.m, 0, 0)])
e.each { |x| def x.used_by?(v) vertices.include?(v) end; def x.other_vertex(v) v == start ? self.end : start end }
m.selection.clear; m.selection.add(e)
UI.answers = [:default]; RW::RoadBuilder.run
# ราคาตัวอย่างเพื่อแสดงหน้าจอเท่านั้น (ไม่ใช่ราคาอ้างอิง)
m.set_attribute('RoadWay_Cost', 'rules', JSON.generate([
  { 'by' => 'label', 'key' => 'คอนกรีตคาน', 'unit' => 'm3', 'price' => 100, 'waste' => 3 },
  { 'by' => 'material', 'key' => 'RW-แอสฟัลต์คอนกรีต', 'unit' => 'm2', 'price' => 10, 'waste' => 0 }
]))
puts JSON.generate(RW::Quantifier.data)
