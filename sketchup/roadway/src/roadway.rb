# RoadWay — ชุดเครื่องมือ SketchUp ภาษาไทย (WANICNSURVEY)
#   1. ตัวสร้างโปรไฟล์ (Profile)  2. ถอดปริมาณ/ราคา (Quantity)  3. เหล็กเสริม (Rebar)
#   + ตัวสร้างถนนตามแนว (Road)
# รองรับ SketchUp 2017 ขึ้นไป (Windows / macOS)
require 'sketchup.rb'
require 'extensions.rb'

module WanicnSurvey
  module RoadWay
    PLUGIN_ID   = 'roadway'.freeze
    PLUGIN_NAME = 'RoadWay'.freeze
    VERSION     = '1.0.0'.freeze
    PLUGIN_DIR  = File.join(File.dirname(__FILE__), PLUGIN_ID)

    unless file_loaded?(__FILE__)
      ext = SketchupExtension.new(PLUGIN_NAME, File.join(PLUGIN_DIR, 'core'))
      ext.description = 'RoadWay: สร้างโปรไฟล์ตามแนว ถนน เหล็กเสริม และถอดปริมาณ/ราคา ' \
                        'ในชุดเดียว (ภาษาไทย)'
      ext.version     = VERSION
      ext.creator     = 'WANICNSURVEY — นายเวนิช ธัมมะวงษ์'
      ext.copyright   = '2026 WANICNSURVEY'
      Sketchup.register_extension(ext, true)
      file_loaded(__FILE__)
    end
  end
end
