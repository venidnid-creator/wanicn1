# ทดสอบส่วนคำนวณที่ไม่พึ่ง SketchUp:  ruby test/test_pure.rb
require 'minitest/autorun'
require 'json'
SRC = File.expand_path('../src/roadway', __dir__)
%w[geo profiles rebar_calc report].each { |f| require File.join(SRC, f) }
RW = WanicnSurvey::RoadWay

class TestGeo < Minitest::Test
  def test_length_and_stations
    pts = [[0, 0, 0], [10, 0, 0], [10, 5, 0]]
    assert_in_delta 15.0, RW::Geo.polyline_length(pts)
    st = RW::Geo.stations(pts, 5, 0)
    assert_equal 4, st.size
    assert_equal [10.0, 5.0, 0.0], st[-1][0]
    assert_equal [0.0, 1.0, 0.0], st[-1][1]
    assert_equal 5, RW::Geo.stations(pts, 4, 0, true).size # 0 4 8 12 + ปลาย 15
  end

  def test_dedupe
    assert_equal 2, RW::Geo.dedupe([[0, 0, 0], [0, 0, 0], [1, 0, 0]]).size
  end
end

class TestProfiles < Minitest::Test
  def test_every_catalog_profile_builds
    RW::Profiles::CATALOG.each do |k, spec|
      loops = RW::Profiles.build(k, spec[:params].map { |p| p[1] })
      assert RW::Profiles.area(loops) > 0, k
    end
  end

  def test_areas
    assert_in_delta 0.02, RW::Profiles.area([RW::Profiles.rect(0.1, 0.2)]), 1e-12
    # I: 2 ปีก + เอว
    a = 2 * 0.1 * 0.008 + 0.0055 * (0.2 - 0.016)
    assert_in_delta a, RW::Profiles.area(RW::Profiles.build('ibeam', [0.2, 0.1, 0.0055, 0.008])), 1e-12
    pipe = RW::Profiles.build('pipe', [0.1, 0.005])
    assert RW::Profiles.area(pipe) < RW::Profiles.area([pipe[0]])
  end

  def test_anchor_and_bad_input
    loops = RW::Profiles.place([RW::Profiles.rect(2, 1)], 'บนซ้าย')
    x0, y0, x1, y1 = RW::Profiles.bbox(loops)
    assert_in_delta 0, x0; assert_in_delta 0, y1; assert_in_delta 2, x1; assert_in_delta(-1, y0)
    assert_raises(ArgumentError) { RW::Profiles.build('rect', [0, 1]) }
    assert_raises(ArgumentError) { RW::Profiles.build('pipe', [0.1, 0.06]) }
  end

  def test_road_section
    o = { lane_w: 3.0, lanes: 1, shoulder_w: 1.0, crown_pct: 2, shoulder_pct: 4,
          layers: [['ผิวทาง', 0.05], ['พื้นทาง', 0.20], ['รองพื้นทาง', 0.0]] }
    s = RW::Profiles.road_section(o)
    assert_equal %w[ผิวทาง พื้นทาง], s.keys
    assert_in_delta 8.0 * 0.05, RW::Profiles.area(s['ผิวทาง']), 1e-9
    assert_in_delta 8.0 * 0.20, RW::Profiles.area(s['พื้นทาง']), 1e-9
    top_edge = s['ผิวทาง'][0].map { |p| p[1] }.max
    assert_in_delta 0.0, top_edge # ระดับหลังถนนที่แนวศูนย์กลาง
  end
end

class TestRebar < Minitest::Test
  C = RW::RebarCalc
  def test_parse
    assert_equal({ kind: 'DB', d: 12, n: 4, s: 0.0, text: 'DB12' }, C.parse('4-DB12'))
    assert_equal 0.15, C.parse('RB6@0.15')[:s]
    assert_equal 'DB', C.parse('SD16')[:kind]
    assert_nil C.parse('12mm')
    assert_raises(ArgumentError) { C.parse!('DB12', :n) }
  end

  def test_weights_and_lap
    assert_in_delta 0.888, C.kg_m(12), 0.001
    assert_in_delta 0.48, C.lap(C.parse('DB12')), 1e-9   # 40d
    assert_in_delta 0.30, C.lap(C.parse('RB6')), 1e-9    # ขั้นต่ำ 0.30
  end

  def test_beam
    r = C.beam(b: 0.2, h: 0.4, L: 4.0, top: '2-DB12', bot: '3-DB16', stirrup: 'RB6@0.15')
    mains = r[:bars].reject { |b| b[:shape] == 'ปลอก' }
    assert_equal 5, mains.size
    # ยาวตัด = L - 2 หุ้ม + ขอ 12d x 2
    assert_in_delta 4.0 - 0.06 + 2 * 0.192, mains.find { |b| b[:bar] == 'DB16' }[:length], 1e-3
    st = r[:bars].select { |b| b[:shape] == 'ปลอก' }
    assert_equal 27, st.size # floor((4.0-0.10)/0.15) + 1 = 26 + 1
    assert_in_delta 2 * (0.2 + 0.4 - 4 * 0.03 - 2 * 0.006) + 0.2, st[0][:length], 0.002
    assert_in_delta 0.32, r[:concrete_m3], 1e-9
    assert_raises(ArgumentError) { C.beam(b: 0.08, h: 0.4, L: 4, top: '6-DB25', bot: '2-DB12', stirrup: 'RB6@0.15') }
  end

  def test_column_positions
    [4, 6, 8, 9, 12].each do |n|
      pts = C.column_positions(n, 0.1, 0.1)
      assert_equal n, pts.size
      assert_equal n, pts.uniq.size
    end
    r = C.column(b: 0.25, h: 0.25, H: 3.0, main: '8-DB16', tie: 'RB6@0.20')
    assert_equal 8, r[:bars].count { |b| b[:bar] == 'DB16' }
    assert_in_delta 3.0 + 0.64, r[:bars].first[:length], 1e-3 # รวมทาบ 40d
  end

  def test_slab_and_cutlist
    r = C.slab(Lx: 4.0, Ly: 3.0, t: 0.10, bars_x: 'RB9@0.20', bars_y: 'RB9@0.20')
    nx = ((3.0 - 0.04) / 0.2).floor + 1
    ny = ((4.0 - 0.04) / 0.2).floor + 1
    assert_equal nx + ny, r[:bars].size
    list = C.cut_list(r[:bars].map { |b| b.merge(count: 1) })
    assert_equal 2, list.size
    assert_equal nx, list.find { |x| x[:mark] == 'S1-BX' }[:count]
    s = C.summary(list)
    total = list.inject(0) { |a, x| a + x[:kg] }
    assert_in_delta total * 1.05, s[:kg], 0.05
    assert_in_delta s[:kg] / 1000 * 20, s[:tie_wire_kg], 0.01
  end
end

class TestReport < Minitest::Test
  R = RW::Report
  ITEMS = [
    { label: 'คานB1', material: 'คอนกรีต', tag: 'A', count: 1, length: 0, area: 2, volume: 0.32, kg: 0 },
    { label: 'คานB1', material: 'คอนกรีต', tag: 'A', count: 1, length: 0, area: 2, volume: 0.32, kg: 0 },
    { label: 'เหล็ก DB12', material: 'เหล็ก', tag: 'B', count: 4, length: 16, area: 0, volume: 0, kg: 14.2 }
  ].freeze

  def test_group_and_cost
    rules = [{ 'by' => 'material', 'key' => 'คอนกรีต', 'unit' => 'm3', 'price' => 2000, 'waste' => 5 },
             { 'by' => 'label', 'key' => 'เหล็ก DB12', 'unit' => 'kg', 'price' => 30, 'waste' => 0 }]
    rows = R.group(ITEMS, :label, rules)
    b1 = rows.find { |r| r[:name] == 'คานB1' }
    assert_equal 2, b1[:count]
    assert_in_delta 0.64 * 1.05 * 2000, b1[:cost], 0.01
    t = R.totals(rows)
    assert_in_delta 0.64 * 1.05 * 2000 + 14.2 * 30, t[:cost], 0.01
    assert_equal 0.0, R.cost(ITEMS[0], [])
  end

  def test_csv
    s = R.csv(%w[a b], [['x,y', 'q"']])
    assert s.start_with?("﻿")
    assert_includes s, '"x,y","q"""'
  end
end
