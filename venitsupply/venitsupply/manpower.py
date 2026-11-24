# SPDX-License-Identifier: GPL-3.0-or-later
"""อัตรากำลังตามสายการบังคับบัญชา: กอง › ฝ่าย › งาน › ตำแหน่ง (กรอบ / มีคนครอง / ว่าง),
มาตรฐานกำหนดตำแหน่ง (ลักษณะงานที่ปฏิบัติแยกตามด้าน), ภาระงานรายตำแหน่ง และการวิเคราะห์ว่าต้องการคนเพิ่มกี่คน.

แม่แบบ อบต.ไม้ขาว มาจาก «แผนอัตรากำลัง 3 ปี ประจำปีงบประมาณ พ.ศ. 2570–2572» (แผนภูมิโครงสร้าง ข้อ 10 และ
บัญชีจัดคนลงสู่ตำแหน่ง ข้อ 11) — เก็บเฉพาะตำแหน่งและจำนวน ไม่เก็บชื่อบุคคล.
"""
from __future__ import annotations

import math
import re

SIDES = ["ด้านการปฏิบัติการ", "ด้านการวางแผน", "ด้านการประสานงาน", "ด้านการบริการ"]
STAFF = {"อ": "อำนวยการท้องถิ่น", "ว": "วิชาการ", "ท": "ทั่วไป", "ภ": "พนักงานจ้างตามภารกิจ",
         "จ": "พนักงานจ้างทั่วไป", "ค": "ครู/บุคลากรทางการศึกษา"}
STAFF_TYPES = list(STAFF.values())
THAI_NUM = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def U(name, kind="งาน", head=None, pos=(), sub=(), aliases=""):
    """A unit of the template: head = (title, level, vacant)."""
    return dict(name=name, kind=kind, head=head, pos=list(pos), sub=list(sub), aliases=aliases)


def _boss(t, lv="ต้น", vac=0):
    return (t, lv, vac)


# (ตำแหน่ง, ระดับ, ประเภท(STAFF), กรอบ, ว่าง)
MAIKHAO_2570 = [
    U("สำนักปลัด", "กอง", _boss("หัวหน้าสำนักปลัด (นักบริหารงานทั่วไป ระดับต้น)", vac=1), aliases="สำนักปลัด,สำนักลัด", sub=[
        U("ฝ่ายอำนวยการ", "ฝ่าย", _boss("หัวหน้าฝ่ายอำนวยการ (นักบริหารงานทั่วไป ระดับต้น)"), sub=[
            U("งานการเจ้าหน้าที่", pos=[("นักทรัพยากรบุคคล", "ปก./ชก.", "ว", 2, 0),
                                       ("ผู้ช่วยนักทรัพยากรบุคคล", "", "ภ", 2, 0),
                                       ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0)]),
            U("งานธุรการ", pos=[("นักจัดการงานทั่วไป", "ปก./ชก.", "ว", 1, 1),
                                ("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 0),
                                ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 2, 0),
                                ("พนักงานขับเครื่องจักรกลขนาดเบา", "", "ภ", 1, 0),
                                ("พนักงานขับรถยนต์", "", "ภ", 2, 0), ("คนงาน", "", "จ", 9, 0),
                                ("แม่บ้าน", "", "จ", 1, 0)]),
            U("งานกิจการสภา", pos=[("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0)]),
            U("งานส่งเสริมการท่องเที่ยว", pos=[("นักพัฒนาการท่องเที่ยว", "ปก./ชก.", "ว", 1, 1),
                                               ("ผู้ช่วยนักพัฒนาการท่องเที่ยว", "", "ภ", 1, 0),
                                               ("ผู้ช่วยเจ้าพนักงานส่งเสริมการท่องเที่ยว", "", "ภ", 1, 0)])]),
        U("ฝ่ายปกครอง", "ฝ่าย", _boss("หัวหน้าฝ่ายปกครอง (นักบริหารงานทั่วไป ระดับต้น)"), sub=[
            U("งานวิเคราะห์นโยบายและแผน", pos=[("นักวิเคราะห์นโยบายและแผน", "ปก./ชก.", "ว", 2, 0),
                                               ("ผู้ช่วยนักวิเคราะห์นโยบายและแผน", "", "ภ", 1, 0)]),
            U("งานนิติการ", pos=[("นิติกร", "ปก./ชก.", "ว", 2, 0), ("ผู้ช่วยนิติกร", "", "ภ", 1, 0)]),
            U("งานประชาสัมพันธ์", pos=[("นักประชาสัมพันธ์", "ปก./ชก.", "ว", 1, 0),
                                       ("นักวิชาการคอมพิวเตอร์", "ปก./ชก.", "ว", 1, 0),
                                       ("ผู้ช่วยนักประชาสัมพันธ์", "", "ภ", 1, 0),
                                       ("ผู้ช่วยเจ้าพนักงานประชาสัมพันธ์", "", "ภ", 1, 0)]),
            U("งานรักษาความสงบ", pos=[("นักจัดการงานเทศกิจ", "ปก./ชก.", "ว", 1, 0),
                                      ("ผู้ช่วยนักจัดการงานเทศกิจ", "", "ภ", 1, 0),
                                      ("พนักงานขับรถยนต์", "", "ภ", 1, 0), ("พนักงานเทศกิจ", "", "จ", 3, 0),
                                      ("คนงาน", "", "จ", 1, 0)])]),
        U("ฝ่ายป้องกันและบรรเทาสาธารณภัย", "ฝ่าย",
          _boss("หัวหน้าฝ่ายป้องกันและบรรเทาสาธารณภัย (นักบริหารงานทั่วไป ระดับต้น)"), sub=[
            U("งานป้องกันและบรรเทาสาธารณภัย", pos=[
                ("นักป้องกันและบรรเทาสาธารณภัย", "ปก./ชก.", "ว", 1, 0),
                ("เจ้าพนักงานป้องกันและบรรเทาสาธารณภัย", "ปง./ชง.", "ท", 1, 1),
                ("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 0),
                ("ผู้ช่วยนักป้องกันและบรรเทาสาธารณภัย", "", "ภ", 1, 0),
                ("ผู้ช่วยเจ้าพนักงานป้องกันและบรรเทาสาธารณภัย", "", "ภ", 1, 1),
                ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0), ("พนักงานขับเครื่องจักรกลขนาดเบา", "", "ภ", 2, 0),
                ("พนักงานขับรถยนต์", "", "ภ", 1, 0), ("พนักงานดับเพลิง (ภารกิจ)", "", "ภ", 4, 0),
                ("พนักงานดับเพลิง (ทั่วไป)", "", "จ", 6, 0)])])]),
    U("กองคลัง", "กอง", _boss("ผู้อำนวยการกองคลัง (นักบริหารงานการคลัง ระดับต้น)"), aliases="กองคลัง", sub=[
        U("ฝ่ายพัฒนารายได้", "ฝ่าย", _boss("หัวหน้าฝ่ายพัฒนารายได้ (นักบริหารงานการคลัง ระดับต้น)", vac=1), sub=[
            U("งานพัฒนารายได้", pos=[("นักวิชาการจัดเก็บรายได้", "ปก./ชก.", "ว", 1, 0),
                                     ("เจ้าพนักงานจัดเก็บรายได้", "ปง./ชง.", "ท", 2, 1),
                                     ("นายช่างเขียนแบบ", "ปง./ชง.", "ท", 1, 1),
                                     ("ผู้ช่วยเจ้าพนักงานจัดเก็บรายได้", "", "ภ", 3, 0), ("คนงาน", "", "จ", 1, 0)])]),
        U("ฝ่ายการเงินและบัญชี", "ฝ่าย", _boss("หัวหน้าฝ่ายการเงินและบัญชี (นักบริหารงานการคลัง ระดับต้น)"), sub=[
            U("งานการเงิน", pos=[("เจ้าพนักงานการเงินและบัญชี", "ปง./ชง.", "ท", 1, 0),
                                 ("ผู้ช่วยเจ้าพนักงานการเงินและบัญชี", "", "ภ", 1, 0),
                                 ("พนักงานขับรถยนต์", "", "ภ", 1, 0)]),
            U("งานบัญชี", pos=[("นักวิชาการเงินและบัญชี", "ปก./ชก.", "ว", 1, 1),
                               ("เจ้าพนักงานการเงินและบัญชี", "ปง./ชง.", "ท", 1, 0),
                               ("ผู้ช่วยนักวิชาการเงินและบัญชี", "", "ภ", 1, 0)]),
            U("งานทะเบียนทรัพย์สินและพัสดุ", pos=[("นักวิชาการพัสดุ", "ปก./ชก.", "ว", 1, 0),
                                                  ("เจ้าพนักงานพัสดุ", "ปง./ชง.", "ท", 2, 0),
                                                  ("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 1),
                                                  ("ผู้ช่วยเจ้าพนักงานพัสดุ", "", "ภ", 1, 0),
                                                  ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0),
                                                  ("คนงาน", "", "จ", 1, 0)])])]),
    U("กองช่าง", "กอง", _boss("ผู้อำนวยการกองช่าง (นักบริหารงานช่าง ระดับต้น)"), aliases="กองช่าง", sub=[
        U("ฝ่ายแบบแผนและก่อสร้าง", "ฝ่าย", _boss("หัวหน้าฝ่ายแบบแผนและก่อสร้าง (นักบริหารงานช่าง ระดับต้น)"), sub=[
            U("งานแบบแผนและก่อสร้าง", pos=[
                ("วิศวกรโยธา", "ปก./ชก.", "ว", 1, 0), ("นักจัดการงานทั่วไป", "ปก./ชก.", "ว", 1, 0),
                ("นายช่างโยธา", "ปง./ชง.", "ท", 1, 1), ("นายช่างเขียนแบบ", "ปง./ชง.", "ท", 1, 0),
                ("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 0), ("พนักงานขับเครื่องจักรกลขนาดกลาง", "", "ภ", 2, 0),
                ("ผู้ช่วยนายช่างโยธา", "", "ภ", 2, 1), ("ผู้ช่วยนายช่างเขียนแบบ", "", "ภ", 1, 0),
                ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0), ("พนักงานขับรถยนต์", "", "ภ", 1, 0),
                ("คนงาน", "", "จ", 1, 0)])]),
        U("ฝ่ายควบคุมอาคาร", "ฝ่าย", _boss("หัวหน้าฝ่ายควบคุมอาคาร (นักบริหารงานช่าง ระดับต้น)"), sub=[
            U("งานสาธารณูปโภค", pos=[
                ("สถาปนิก", "ปก./ชก.", "ว", 1, 1), ("นายช่างไฟฟ้า", "ปง./ชง.", "ท", 1, 1),
                ("เจ้าพนักงานประปา", "ปง./ชง.", "ท", 1, 1), ("ผู้ช่วยนายช่างโยธา", "", "ภ", 1, 1),
                ("ผู้ช่วยนายช่างไฟฟ้า", "", "ภ", 2, 1), ("ผู้ช่วยเจ้าพนักงานประปา", "", "ภ", 2, 0),
                ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0), ("พนักงานขับเครื่องจักรกลขนาดเบา", "", "ภ", 2, 0),
                ("คนงานประปา", "", "จ", 2, 0), ("พนักงานจดมาตรวัดน้ำ", "", "จ", 2, 0)]),
            U("งานผังเมือง", pos=[("นายช่างโยธา", "ปง./ชง.", "ท", 1, 0), ("ผู้ช่วยนายช่างโยธา", "", "ภ", 1, 0),
                                  ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0)])])]),
    U("กองสาธารณสุขและสิ่งแวดล้อม", "กอง",
      _boss("ผู้อำนวยการกองสาธารณสุขและสิ่งแวดล้อม (นักบริหารงานสาธารณสุขและสิ่งแวดล้อม ระดับต้น)", vac=1),
      aliases="กองสาธารณสุข,กองสาธารณสุขฯ,กองสาธารณสุขและสิ่งแวดล้อม", sub=[
        U("ฝ่ายบริหารงานสาธารณสุข", "ฝ่าย",
          _boss("หัวหน้าฝ่ายบริหารงานสาธารณสุข (นักบริหารงานสาธารณสุขและสิ่งแวดล้อม ระดับต้น)", vac=1), sub=[
            U("งานส่งเสริมสุขภาพ", pos=[("นักวิชาการสาธารณสุข", "ปก./ชก.", "ว", 1, 1),
                                        ("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 0),
                                        ("ผู้ช่วยนักวิชาการสาธารณสุข", "", "ภ", 1, 0)]),
            U("งานบริการสาธารณสุข", pos=[("เจ้าพนักงานสาธารณสุข", "ปง./ชง.", "ท", 2, 0),
                                         ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0),
                                         ("พนักงานขับรถยนต์", "", "ภ", 5, 1), ("คนงาน", "", "จ", 4, 0),
                                         ("พนักงานกู้ชีพ", "", "จ", 3, 0)]),
            U("งานส่งเสริมสิ่งแวดล้อม", pos=[("นักวิชาการสุขาภิบาล", "ปก./ชก.", "ว", 1, 1),
                                             ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0),
                                             ("พนักงานขับเครื่องจักรกลขนาดกลาง", "", "ภ", 1, 0),
                                             ("พนักงานขับรถยนต์", "", "ภ", 2, 1), ("คนงาน", "", "จ", 2, 0),
                                             ("คนงานประจำรถบรรทุกขยะ", "", "จ", 12, 2)])])]),
    U("กองการศึกษา ศาสนา และวัฒนธรรม", "กอง",
      _boss("ผู้อำนวยการกองการศึกษา (นักบริหารงานการศึกษา ระดับต้น)"),
      aliases="กองการศึกษา,กองการศึกษาฯ,กองการศึกษา ศาสนา และวัฒนธรรม,กองการศึกษา ศาสนาและวัฒนธรรม", sub=[
        U("ฝ่ายบริหารการศึกษา", "ฝ่าย", _boss("หัวหน้าฝ่ายบริหารการศึกษา (นักบริหารงานการศึกษา ระดับต้น)", vac=1), sub=[
            U("งานบริหารงานทั่วไป", pos=[("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 0),
                                         ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0),
                                         ("พนักงานขับรถยนต์", "", "ภ", 1, 0), ("คนงาน", "", "จ", 3, 0)]),
            U("งานส่งเสริมการศึกษา ศาสนาและวัฒนธรรม", pos=[("นักวิชาการศึกษา", "ปก./ชก.", "ว", 1, 0),
                                                            ("ผู้ช่วยนักวิชาการศึกษา", "", "ภ", 1, 0)]),
            U("งานบริหารการศึกษา", pos=[("นักวิชาการศึกษา", "ปก./ชก.", "ว", 1, 0),
                                        ("ผู้ช่วยนักวิชาการศึกษา", "", "ภ", 1, 0),
                                        ("พนักงานขับรถยนต์", "", "ภ", 1, 0)], sub=[
                U("ศูนย์พัฒนาเด็กเล็กบ้านท่าฉัตรไชย", "หน่วยงานย่อย", pos=[
                    ("ผู้อำนวยการศูนย์พัฒนาเด็กเล็ก", "", "ค", 1, 1), ("ครู", "คศ.", "ค", 2, 0),
                    ("ผู้ดูแลเด็ก (ทักษะ)", "", "ภ", 3, 0)]),
                U("ศูนย์พัฒนาเด็กเล็กตำบลไม้ขาว", "หน่วยงานย่อย", pos=[
                    ("ผู้อำนวยการศูนย์พัฒนาเด็กเล็ก", "", "ค", 1, 1), ("ครู", "คศ.", "ค", 5, 1),
                    ("ผู้ช่วยครูผู้ช่วย", "", "ภ", 4, 0), ("ผู้ดูแลเด็ก (ทักษะ)", "", "ภ", 5, 2),
                    ("นักการภารโรง", "", "จ", 1, 1)])]),
            U("งานส่งเสริมกีฬาและนันทนาการ", pos=[("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0)])])]),
    U("กองสวัสดิการสังคม", "กอง", _boss("ผู้อำนวยการกองสวัสดิการสังคม (นักบริหารงานสวัสดิการสังคม ระดับต้น)"),
      aliases="กองสวัสดิการสังคม,กองสวัสดิการ", sub=[
        U("ฝ่ายส่งเสริมสวัสดิการสังคม", "ฝ่าย",
          _boss("หัวหน้าฝ่ายส่งเสริมสวัสดิการสังคม (นักบริหารงานสวัสดิการสังคม ระดับต้น)"), sub=[
            U("งานพัฒนาชุมชน", pos=[("นักพัฒนาชุมชน", "ปก./ชก.", "ว", 1, 0), ("เจ้าพนักงานธุรการ", "ปง./ชง.", "ท", 1, 0),
                                    ("ผู้ช่วยนักพัฒนาชุมชน", "", "ภ", 2, 0), ("พนักงานขับรถยนต์", "", "ภ", 1, 0)]),
            U("งานสังคมสงเคราะห์", pos=[("นักสังคมสงเคราะห์", "ปก./ชก.", "ว", 1, 1),
                                        ("ผู้ช่วยนักสังคมสงเคราะห์", "", "ภ", 1, 0),
                                        ("ผู้ช่วยเจ้าพนักงานธุรการ", "", "ภ", 1, 0)])])]),
    U("หน่วยตรวจสอบภายใน", "กอง", aliases="หน่วยตรวจสอบภายใน,ตรวจสอบภายใน", pos=[
        ("นักวิชาการตรวจสอบภายใน", "ปก./ชก.", "ว", 1, 1), ("ผู้ช่วยนักวิชาการตรวจสอบภายใน", "", "ภ", 1, 0)]),
]

# ตัวอย่างมาตรฐานกำหนดตำแหน่งที่เจ้าของส่งมา (บรรณารักษ์ — ก.ท. กำหนดเมื่อ 26 พฤศจิกายน 2558)
# ข้อความตำแหน่งอื่นให้เจ้าหน้าที่วาง/พิมพ์จากมาตรฐานกำหนดตำแหน่งของตำแหน่งนั้น
SAMPLE_STANDARD = ("บรรณารักษ์", """
๑. ด้านการปฏิบัติการ
๑.๑ จัดหา คัดเลือก วิเคราะห์ จำแนกหมวดหมู่ทรัพยากรสารสนเทศ ประเภทสื่อสิ่งพิมพ์ สื่อโสตทัศน์ และสื่ออิเล็กทรอนิกส์ ทำรายการบรรณานุกรม ดัชนีวารสาร สาระสังเขป และบันทึกลงฐานข้อมูลระบบห้องสมุดอัตโนมัติ เพื่อเป็นแหล่งจัดเก็บและให้บริการ
๑.๒ ให้บริการยืม-คืน สืบค้น ตอบคำถาม และช่วยการค้นคว้า รวมถึงจัดทำคู่มือการใช้งานห้องสมุด เพื่อให้ผู้ใช้บริการสามารถเข้าถึงทรัพยากรได้อย่างมีประสิทธิภาพสูงสุดและเกิดประโยชน์ต่อการค้นคว้าเอกสาร หนังสือ และรายงานต่างๆ ของผู้ใช้บริการมากที่สุด
๑.๓ จัดทำดรรชนีวารสาร บรรณานุกรมหนังสือ และกฤตภาคหัวเรื่องที่น่าสนใจ เพื่อให้งานด้านห้องสมุดเป็นไปอย่างมีประสิทธิภาพ
๑.๔ ศึกษา วิเคราะห์ และสอบถามความต้องการของผู้ใช้บริการ และบุคลากรต่างๆ ที่เกี่ยวข้อง รวมทั้งรับผิดชอบ และดูแลทรัพยากรห้องสมุด เช่น หนังสือ สิ่งตีพิมพ์ CD-Rom เป็นต้น เพื่อให้มีทรัพยากรที่เพียงพอในการให้บริการ สอดคล้องความต้องการ และเกิดประโยชน์แก่ผู้ใช้บริการมากที่สุด
๑.๕ ศึกษา ค้นคว้า วิธีการและเทคนิคใหม่ๆ การใช้เครื่องมืออุปกรณ์ที่ทันสมัยด้านบรรณารักษศาสตร์และสารนิเทศศาสตร์ เพื่อเสนอแนะและปรับปรุงการปฏิบัติงานห้องสมุด ทั้งด้านวิชาการและการให้บริการ
๑.๖ ศึกษา และติดตามเทคโนโลยีองค์ความรู้ใหม่ๆ กฎหมาย และระเบียบต่างๆ ที่เกี่ยวข้องกับงานบรรณารักษ์ เพื่อนำมาประยุกต์ใช้ในการปฏิบัติงานได้อย่างมีประสิทธิภาพสูงสุด
๑.๗ ศึกษา และสอบถามความต้องการของผู้ใช้บริการ และบุคลากรต่างๆ ที่เกี่ยวข้อง รวมทั้งรับผิดชอบ และดูแลทรัพยากรห้องสมุด เช่น หนังสือ สิ่งตีพิมพ์ CD-Rom เป็นต้น เพื่อให้มีทรัพยากรที่เพียงพอในการให้บริการ สอดคล้องความต้องการ และเกิดประโยชน์แก่ผู้ใช้บริการมากที่สุด
๑.๘ จัดทำสื่อประชาสัมพันธ์การใช้ห้องสมุดและจัดกิจกรรมในรูปแบบต่าง ๆ เพื่อเผยแพร่ข้อมูลข่าวสาร และส่งเสริมให้ผู้ใช้เกิดความสนใจในการเข้าใช้บริการ
๒. ด้านการวางแผน
๒.๑ วางแผนการทำงานที่รับผิดชอบร่วมดำเนินการวางแผนการทำงานของหน่วยงานหรือโครงการเพื่อให้การดำเนินงานเป็นไปตามเป้าหมายผลสัมฤทธิ์ที่กำหนด
๒.๒ วางแผนการปฏิบัติงานของห้องสมุด โดยศึกษา และวิเคราะห์จากข้อมูลที่เกี่ยวข้องต่างๆ เช่น รายงานความต้องการของกลุ่มเป้าหมาย สถิติข้อมูลการดำเนินงาน เป็นต้น เพื่อให้เกิดประสิทธิภาพในการให้บริการ และครอบคลุมกลุ่มเป้าหมาย
๒.๓ เสนอแนะประเด็นสำคัญหรือกิจกรรมต่างๆ เกี่ยวกับห้องสมุด และห้องสมุดเคลื่อนที่ เพื่อเป็นประโยชน์ประกอบการวางแผน และออกแบบนโยบาย แผนการ แนวทาง หลักเกณฑ์ และมาตรการต่างๆ ของห้องสมุด
๓. ด้านการประสานงาน
๓.๑ ประสานการทำงานร่วมกันทั้งภายในและภายนอกทีมงานหรือหน่วยงาน เพื่อให้เกิดความร่วมมือและผลสัมฤทธิ์ตามที่กำหนดไว้
๓.๒ ชี้แจงและให้รายละเอียดเกี่ยวกับข้อมูล ข้อเท็จจริง แก่บุคคลหรือหน่วยงานที่เกี่ยวข้อง เพื่อสร้างความเข้าใจหรือความร่วมมือในการดำเนินงานตามที่ได้รับมอบหมาย
๔. ด้านการบริการ
๔.๑ ให้คำแนะนำ และตอบคำถามเกี่ยวกับข้อมูล และการใช้ทรัพยากรสารสนเทศในห้องสมุดเพื่อให้เกิดความสะดวกแก่ผู้ใช้บริการและประชาชน
""")


def parse_standard(text: str) -> list[tuple[str, str]]:
    """Text pasted from a มาตรฐานกำหนดตำแหน่ง → [(ด้าน, ลักษณะงาน)].

    Headings like «๑. ด้านการปฏิบัติการ»; items «๑.๑ …» (Thai or Arabic digits) — wrapped lines are joined;
    text before the first heading, «หน้าที่และความรับผิดชอบหลัก» and «คุณสมบัติเฉพาะ…» (and after) are ignored."""
    out: list[list[str]] = []
    side = None
    for raw in (text or "").splitlines():
        line = raw.strip().translate(THAI_NUM)
        if not line:
            continue
        if line.startswith("คุณสมบัติเฉพาะ"):
            break
        m = re.match(r"^\d+\s*[.)]\s*(ด้าน\S.*)$", line) or re.match(r"^(ด้าน\S+)$", line)
        if m:
            name = re.sub(r"\s+", "", m.group(1))
            side = next((s for s in SIDES if s.replace(" ", "") == name), m.group(1).strip())
            continue
        if side is None:
            continue
        m = re.match(r"^\d+\s*\.\s*\d+\s*\.?\s*(.+)$", line)
        if m:
            out.append([side, m.group(1).strip()])
        elif out and out[-1][0] == side:
            out[-1][1] += ("" if out[-1][1].endswith(" ") else " ") + line
        elif re.match(r"^[-•]", line):
            out.append([side, line.lstrip("-• ").strip()])
        else:
            out.append([side, line])
    return [(a, re.sub(r"\s+", " ", b)) for a, b in out]


def base_title(title: str) -> str:
    """«นักวิชาการพัสดุ (ปก./ชก.)» → «นักวิชาการพัสดุ»; «ครู» stays."""
    t = re.sub(r"\((?:ปก|ชก|ปง|ชง|ปฏิบัติ|ชำนาญ)[^)]*\)", "", title or "")
    t = re.sub(r"\s+(?:ปฏิบัติการ|ชำนาญการ|ปฏิบัติงาน|ชำนาญงาน)$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()


def need_people(fte: float) -> int:
    """จำนวนคนที่ต้องการจาก FTE: ปัดเศษ (ตั้งแต่ .50 ขึ้น) และอย่างน้อย 1 เมื่อมีภาระงาน."""
    if fte <= 0:
        return 0
    return max(1, int(math.floor(fte + 0.5)))


SQL = """
CREATE TABLE IF NOT EXISTS duties(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, side TEXT NOT NULL, seq INTEGER DEFAULT 0, text TEXT NOT NULL,
  source TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS pos_load(
  id INTEGER PRIMARY KEY, position_id INTEGER NOT NULL REFERENCES positions(id), duty_id INTEGER,
  side TEXT DEFAULT '', task TEXT NOT NULL, seq INTEGER DEFAULT 0, minutes REAL DEFAULT 0, volume REAL DEFAULT 0,
  y1 REAL DEFAULT 0, y2 REAL DEFAULT 0, y3 REAL DEFAULT 0);
"""


class ManpowerMixin:
    """อัตรากำลัง มาตรฐานกำหนดตำแหน่ง ภาระงาน — methods of :class:`venitsupply.db.Store`."""

    def _manpower_init(self):
        self.con.executescript(SQL)
        for table, col, decl in (("positions", "level", "TEXT DEFAULT ''"), ("positions", "occupied", "INTEGER"),
                                 ("positions", "seq", "INTEGER DEFAULT 0"), ("positions", "is_head", "INTEGER DEFAULT 0"),
                                 ("positions", "position_no", "TEXT DEFAULT ''"),
                                 ("hire_tasks", "side", "TEXT DEFAULT ''"), ("hire_tasks", "duty_id", "INTEGER"),
                                 ("hire_jobs", "position_id", "INTEGER")):
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.con.commit()

    # ------------------------------------------------------- structure
    def seed_manpower(self, template=None, replace=False) -> dict:
        """สร้างโครงสร้าง กอง › ฝ่าย › งาน › ตำแหน่ง จากแม่แบบ (ค่าเริ่มต้น: อบต.ไม้ขาว แผนอัตรากำลัง 2570–2572)."""
        template = MAIKHAO_2570 if template is None else template
        if self.q("SELECT 1 FROM divisions"):
            if not replace:
                raise ValueError("มีโครงสร้างหน่วยงานอยู่แล้ว")
            if self.q("SELECT 1 FROM hire_contracts WHERE status='ทำสัญญาแล้ว'"):
                raise ValueError("มีสัญญาจ้างที่ยังมีผลอยู่ — แก้โครงสร้างทีละหน่วยงานแทนการแทนที่ทั้งหมด")
            self.con.execute("UPDATE budget_items SET division_id=NULL")
            self.con.execute("UPDATE procurements SET division_id=NULL")
            self.con.execute("UPDATE hire_jobs SET division_id=NULL, position_id=NULL")
            self.con.execute("UPDATE hire_contracts SET division_id=NULL")
            self.con.execute("DELETE FROM pos_load")
            self.con.execute("DELETE FROM positions")
            self.con.execute("DELETE FROM divisions")
        n = dict(units=0, positions=0, frame=0, vacant=0)

        def add(u, parent):
            short = u["head"][0].split(" (")[0] if u.get("head") else ""
            did = self.save_division(dict(parent_id=parent, kind=u["kind"], name=u["name"],
                                          aliases=u.get("aliases", ""), head_pos=short))
            n["units"] += 1
            seq = 0
            if u.get("head"):
                t, lv, vac = u["head"]
                seq += 1
                self.save_position(dict(division_id=did, title=t, level=lv, line="วิชาการ", kind=STAFF["อ"],
                                        count=1, occupied=1 - vac, is_head=1, seq=seq))
                n["positions"] += 1
                n["frame"] += 1
                n["vacant"] += vac
            for t, lv, st, frame, vac in u.get("pos", []):
                seq += 1
                line = "วิชาการ" if st in ("ว", "ค", "อ") or t.startswith(("ผู้ช่วยนัก", "ผู้ช่วยนิติกร")) else "ทั่วไป"
                self.save_position(dict(division_id=did, title=t, level=lv, line=line, kind=STAFF[st],
                                        count=frame, occupied=frame - vac, seq=seq))
                n["positions"] += 1
                n["frame"] += frame
                n["vacant"] += vac
            for s in u.get("sub", []):
                add(s, did)
        for u in template:
            add(u, None)
        self.con.commit()
        return n

    def descendants(self, did) -> list[int]:
        out, stack = [], [did]
        while stack:
            d = stack.pop()
            out.append(d)
            stack += [r["id"] for r in self.q("SELECT id FROM divisions WHERE parent_id=?", (d,))]
        return out

    def chain(self, did) -> list:
        """หน่วยงานจากล่างขึ้นบน (งาน → ฝ่าย → กอง)."""
        out, d = [], self.division(did) if did else None
        while d is not None:
            out.append(d)
            d = self.division(d["parent_id"]) if d["parent_id"] else None
        return out

    def route(self, did, include_supply=True) -> list[tuple[str, str, str]]:
        """เส้นทางเสนอเอกสาร ตามสายการบังคับบัญชา: [(บทบาท, ชื่อ, ตำแหน่ง)] เจ้าของเรื่อง → … → นายก."""
        st = self.settings()
        out = []
        units = self.chain(did) if did else []
        if units:
            u0 = units[0]
            out.append(("ผู้เสนอ", u0["officer_name"] or "", u0["officer_pos"] or f"เจ้าหน้าที่{u0['name']}"))
        for u in units:
            if u["kind"] in ("ฝ่าย", "กอง") and (u["head_pos"] or u["head_name"]):
                out.append((f"ความเห็น{u['head_pos'] or 'หัวหน้า' + u['name']}", u["head_name"] or "", u["head_pos"] or ""))
        if include_supply:
            fin = st.get("head_officer_pos") or ""
            if fin in ("", "หัวหน้าเจ้าหน้าที่"):
                fin = "ผู้อำนวยการกองคลัง"
            sup = ("ความเห็นเจ้าหน้าที่", st.get("officer") or "", st.get("officer_pos") or "เจ้าหน้าที่พัสดุ")
            i = next((k for k, (_, _, pos) in enumerate(out) if pos and pos == fin), None)
            if i is not None:          # เรื่องของกองคลังเอง: ผอ.กองคลังให้ความเห็นในฐานะหัวหน้าเจ้าหน้าที่ด้วย
                role, name, pos = out[i]
                out[i] = (f"ความเห็น{fin}/หัวหน้าเจ้าหน้าที่", name or st.get("head_officer") or "", pos)
                out.insert(i, sup)
            else:
                out.append(sup)
                out.append((f"ความเห็น{fin}/หัวหน้าเจ้าหน้าที่", st.get("head_officer") or "", fin))
        out.append(("ความเห็นปลัด", st.get("palad") or "", st.get("palad_pos") or "ปลัดองค์การบริหารส่วนตำบล"))
        hp = st.get("head_pos") or ""
        out.append(("คำสั่ง", st.get("head") or "", "นายกองค์การบริหารส่วนตำบล" if hp in ("", "หัวหน้าหน่วยงานของรัฐ")
                    else hp))
        return out

    # ------------------------------------------------------- standards
    def duty_titles(self) -> list[str]:
        rows = {base_title(r["title"]) for r in self.q("SELECT DISTINCT title FROM positions")}
        rows |= {r["title"] for r in self.q("SELECT DISTINCT title FROM duties")}
        rows |= {base_title(r["title"]) for r in self.q("SELECT DISTINCT title FROM hire_jobs")}
        return sorted(t for t in rows if t)

    def duties(self, title):
        return self.q("SELECT * FROM duties WHERE title=? ORDER BY seq, id", (base_title(title),))

    def save_duty(self, data: dict, did=None) -> int:
        d = {k: data[k] for k in ("title", "side", "seq", "text", "source") if k in data}
        if "title" in d:
            d["title"] = base_title(d["title"])
        if "text" in d and not str(d["text"]).strip():
            raise ValueError("กรอกลักษณะงานที่ปฏิบัติ")
        if did:
            self.run(f"UPDATE duties SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), did))
            self.run("UPDATE pos_load SET task=?, side=? WHERE duty_id=?",
                     (self.one("SELECT text FROM duties WHERE id=?", (did,))["text"],
                      self.one("SELECT side FROM duties WHERE id=?", (did,))["side"], did))
            self.run("UPDATE hire_tasks SET task=?, side=? WHERE duty_id=?",
                     (self.one("SELECT text FROM duties WHERE id=?", (did,))["text"],
                      self.one("SELECT side FROM duties WHERE id=?", (did,))["side"], did))
            return did
        if "seq" not in d:
            d["seq"] = (self.one("SELECT IFNULL(MAX(seq),0) AS s FROM duties WHERE title=?", (d["title"],))["s"] or 0) + 1
        return self.run(f"INSERT INTO duties({','.join(d)}) VALUES({','.join('?' * len(d))})", tuple(d.values()))

    def delete_duty(self, did):
        self.run("DELETE FROM pos_load WHERE duty_id=?", (did,))
        self.run("UPDATE hire_tasks SET duty_id=NULL WHERE duty_id=?", (did,))
        self.run("DELETE FROM duties WHERE id=?", (did,))

    def move_duty(self, did, step):
        d = self.one("SELECT * FROM duties WHERE id=?", (did,))
        rows = [r["id"] for r in self.duties(d["title"])]
        i = rows.index(did)
        j = max(0, min(len(rows) - 1, i + step))
        rows.insert(j, rows.pop(i))
        for k, rid in enumerate(rows, 1):
            self.con.execute("UPDATE duties SET seq=? WHERE id=?", (k, rid))
        self.con.commit()

    def import_standard(self, title, text, replace=False, source="") -> int:
        items = parse_standard(text)
        if not items:
            raise ValueError("ไม่พบหัวข้อ «๑. ด้านการปฏิบัติการ» และข้อย่อย «๑.๑ …» ในข้อความ")
        title = base_title(title)
        if replace:
            for r in self.duties(title):
                self.delete_duty(r["id"])
        have = {(r["side"], r["text"]) for r in self.duties(title)}
        n = 0
        for side, text_ in items:
            if (side, text_) not in have:
                self.save_duty(dict(title=title, side=side, text=text_, source=source))
                n += 1
        return n

    # ----------------------------------------------------- workload
    def pos_load(self, pid):
        return self.q("SELECT * FROM pos_load WHERE position_id=? ORDER BY seq, id", (pid,))

    def set_pos_load(self, pid, rows):
        """rows: dicts(duty_id?, side, task, minutes, volume, y1, y2, y3)."""
        self.con.execute("DELETE FROM pos_load WHERE position_id=?", (pid,))
        for i, r in enumerate(rows, 1):
            self.con.execute("INSERT INTO pos_load(position_id,duty_id,side,task,seq,minutes,volume,y1,y2,y3) "
                             "VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (pid, r.get("duty_id"), r.get("side", ""), r["task"], i, float(r.get("minutes") or 0),
                              float(r.get("volume") or 0), float(r.get("y1") or 0), float(r.get("y2") or 0),
                              float(r.get("y3") or 0)))
        self.con.commit()

    def load_rows_from_standard(self, pid) -> list[dict]:
        """ลักษณะงานของตำแหน่ง: ที่บันทึกไว้ + ข้อที่ยังไม่มีจากมาตรฐานกำหนดตำแหน่ง (ค่าว่างให้เจ้าหน้าที่เติมเอง)."""
        p = self.one("SELECT * FROM positions WHERE id=?", (pid,))
        have = [dict(r) for r in self.pos_load(pid)]
        used = {r["duty_id"] for r in have if r["duty_id"]}
        for d in self.duties(p["title"]):
            if d["id"] not in used:
                have.append(dict(duty_id=d["id"], side=d["side"], task=d["text"], minutes=0, volume=0, y1=0, y2=0, y3=0))
        order = {s: i for i, s in enumerate(SIDES)}
        have.sort(key=lambda r: (order.get(r["side"], 9), r.get("seq") or 999))
        return have

    def position_analysis(self, pid) -> dict:
        p = self.one("SELECT * FROM positions WHERE id=?", (pid,))
        per = float(self.setting("work_minutes_year") or 82800)
        rows = self.pos_load(pid)
        fte = round(sum(round((r["minutes"] or 0) * (r["volume"] or 0) / per, 2) for r in rows), 2)
        frame = int(p["count"] or 0)
        occ = int(p["occupied"] if p["occupied"] is not None else frame)
        need = need_people(fte) if rows and fte > 0 else None
        short = (need - occ) if need is not None else None
        return dict(position=p, fte=fte, frame=frame, occupied=occ, vacant=max(0, frame - occ), need=need,
                    short=short, has_load=bool(rows and fte > 0),
                    total=sum((r["minutes"] or 0) * (r["volume"] or 0) for r in rows))

    def unit_analysis(self, did) -> dict:
        """รวมทุกตำแหน่งของหน่วยงานและหน่วยงานย่อย."""
        t = dict(frame=0, occupied=0, vacant=0, fte=0.0, need=0, short=0, analysed=0, positions=0)
        for d in self.descendants(did):
            for p in self.positions(d):
                a = self.position_analysis(p["id"])
                t["positions"] += 1
                for k in ("frame", "occupied", "vacant"):
                    t[k] += a[k]
                if a["has_load"]:
                    t["analysed"] += 1
                    t["fte"] += a["fte"]
                    t["need"] += a["need"]
                    t["short"] += max(0, a["short"])
        t["fte"] = round(t["fte"], 2)
        return t

    def manpower_rows(self, did=None) -> list[dict]:
        """Rows for the analysis table: a unit row then its positions, in tree order."""
        out = []

        def walk(d, depth):
            out.append(dict(kind="unit", division=d, depth=depth, **self.unit_analysis(d["id"])))
            for p in self.positions(d["id"]):
                out.append(dict(kind="position", division=d, depth=depth + 1, **self.position_analysis(p["id"])))
            for c in self.divisions(d["id"]):
                walk(c, depth + 1)
        roots = [self.division(did)] if did else self.divisions()
        for d in roots:
            walk(d, 0)
        return out

    def job_from_position(self, pid, division_id=None) -> int:
        """งานจ้างเหมาจากตำแหน่ง: คัดลอกลักษณะงานและปริมาณงาน (เฉพาะที่เติมค่าแล้ว)."""
        p = self.one("SELECT * FROM positions WHERE id=?", (pid,))
        title = base_title(p["title"])
        line = p["line"] or "ทั่วไป"
        qual = "ปริญญาตรี" if line == "วิชาการ" else "ปวส./อนุปริญญา"
        unit = re.sub(r"^งาน", "", self.division(p["division_id"])["name"]).strip()
        a = self.position_analysis(pid)
        # จ้างเหมาเฉพาะส่วนที่เกินกำลังคนที่มีอยู่: ปริมาณงานแต่ละข้อ × (ภาระงาน − คนครอง) ÷ ภาระงาน
        scale = 1.0
        if a["has_load"] and a["occupied"] and a["fte"] > a["occupied"]:
            scale = (a["fte"] - a["occupied"]) / a["fte"]
        note = (f"ตำแหน่ง{title} มีภาระงานเทียบได้ {a['fte']:.2f} คน มีผู้ปฏิบัติงาน {a['occupied']} คน "
                f"ส่วนที่เกิน {max(0.0, a['fte'] - a['occupied']):.2f} คน จ้างเหมาบริการตามปริมาณงานส่วนนี้")
        # ชื่องานจ้างเหมาไม่ใช้ชื่อตำแหน่งของพนักงาน (มุ่งผลสำเร็จของงาน ไม่ใช่การจ้างแรงงาน — ว 877, ว 727)
        jid = self.save_job(dict(division_id=division_id or p["division_id"], title=f"ปฏิบัติงานด้าน{unit}",
                                 line=line, qualification=qual, difficulty=0, background=note))
        self.run("UPDATE hire_jobs SET position_id=? WHERE id=?", (pid, jid))
        rows = [r for r in self.pos_load(pid) if (r["minutes"] or 0) and (r["volume"] or 0)]
        for i, r in enumerate(rows, 1):
            vol = max(1, round(r["volume"] * scale))
            self.con.execute("INSERT INTO hire_tasks(job_id,seq,task,minutes,volume,side,duty_id) VALUES(?,?,?,?,?,?,?)",
                             (jid, i, r["task"], r["minutes"], vol, r["side"], r["duty_id"]))
        self.con.commit()
        return jid
