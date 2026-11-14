# ถนนตามแนว: หน้าตัดผิวจราจร ไหล่ทาง และชั้นโครงสร้างทาง กวาดตามแนวศูนย์กลาง
module WanicnSurvey
  module RoadWay
    module RoadBuilder
      module_function

      SURFACES = { 'แอสฟัลต์คอนกรีต' => [60, 60, 62], 'คอนกรีต' => [190, 190, 185],
                   'ลูกรัง' => [190, 120, 70] }.freeze

      def run
        path = RoadWay.selected_path or return
        r = RoadWay.ask(:road,
                        ['ผิวจราจรกว้างต่อช่อง (ม.)', 'จำนวนช่องจราจรต่อข้าง', 'ไหล่ทางกว้างต่อข้าง (ม.)',
                         'ความลาดผิวจราจร (%)', 'ความลาดไหล่ทาง (%)', 'ชนิดผิวทาง',
                         'ผิวทางหนา (ม.)', 'พื้นทางหนา (ม.)', 'รองพื้นทางหนา (ม.)', 'ชื่อถนน'],
                        ['3.00', '1', '1.00', '2', '4', SURFACES.keys[0], '0.05', '0.20', '0.20', 'ถนนสาย 1'],
                        ['', '', '', '', '', SURFACES.keys.join('|'), '', '', '', ''],
                        'RoadWay — ถนนตามแนว (กรอกตามแบบมาตรฐานที่ใช้)') or return
        o = { lane_w: r[0].to_f, lanes: [r[1].to_i, 1].max, shoulder_w: [r[2].to_f, 0].max,
              crown_pct: r[3].to_f, shoulder_pct: r[4].to_f,
              layers: [['ผิวทาง', r[6].to_f], ['พื้นทาง', r[7].to_f], ['รองพื้นทาง', r[8].to_f]] }
        if o[:lane_w] <= 0
          UI.messagebox('ความกว้างช่องจราจรต้องมากกว่า 0')
          return
        end
        colors = { 'ผิวทาง' => SURFACES[r[5]], 'พื้นทาง' => [150, 140, 120], 'รองพื้นทาง' => [175, 155, 120] }
        width = 2 * (o[:lane_w] * o[:lanes] + o[:shoulder_w])
        RoadWay.operation('RoadWay: ถนนตามแนว') do
          model = Sketchup.active_model
          len = Sweep.length_m(path[:points])
          road = model.active_entities.add_group
          road.name = r[9]
          Profiles.road_section(o).each do |name, loops|
            mat = RoadWay.material("RW-#{name == 'ผิวทาง' ? r[5] : name}", Sketchup::Color.new(*colors[name]))
            g = Sweep.sweep(road.entities, loops, path[:points], "#{name} — #{r[9]}", mat)
            area = Profiles.area(loops)
            data = { kind: 'road', label: name, road: r[9], length_m: len, section_m2: area,
                     volume_m3: area * len }
            data[:area_m2] = width * len if name == 'ผิวทาง'
            RoadWay.stamp(g, data)
          end
          road.layer = RoadWay.tag('RW-ถนน')
          RoadWay.stamp(road, kind: 'element', element: 'road', label: r[9], length_m: len, width_m: width)
          model.selection.clear
          model.selection.add(road)
          road
        end
      end
    end
  end
end
