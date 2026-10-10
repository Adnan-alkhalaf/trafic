import cv2
import time
import numpy as np
from ultralytics import YOLO

class VehicleTracker:

    def __init__(self):
        # تحميل النموذج المعتمد حصرياً بالمشروع YOLO11n
        self.model = YOLO("yolo11n.pt")

        # المعرفات التي عبرت خطوط العد لمنع التكرار
        self.counted_ids = set()

        # المواقع السابقة للمركبات لتتبع العبور والاتجاه
        self.previous_positions = {}
        
        # بصمة الوقت والإحداثيات لتقدير السرعة الحركية
        self.speed_tracker = {}

        # العدادات الإجمالية العامة
        self.total_count = 0
        self.going_count = 0
        self.returning_count = 0

        # عدادات الفئات الستة المطلوبة بالتوصيف بدقة
        self.category_counts = {
            "car": 0,
            "van": 0,
            "bus": 0,
            "truck": 0,
            "motorcycle": 0,
            "traffic-police motorcycle": 0
        }

        # هيكلية تعرفة الرسوم المحددة لكل نوع
        self.rates = {
            "car": 1.0,
            "van": 1.5,
            "bus": 2.0,
            "truck": 2.5,
            "motorcycle": 0.0,
            "traffic-police motorcycle": 0.0
        }
        
        self.total_revenue = 0.0

        # حد السرعة الأقصى الافتراضي X
        self.speed_limit = 60.0

        # تلوين الإطارات (حجز اللون الأحمر حصرياً للمركبات المخالفة)
        # صيغة الألوان في OpenCV هي BGR
        self.colors = {
            "car": (255, 0, 0),                         # أزرق
            "van": (0, 255, 0),                         # أخضر
            "bus": (255, 255, 0),                       # سماوي
            "truck": (255, 0, 255),                     # بنفسجي
            "traffic-police motorcycle": (0, 165, 255), # برتقالي
            "motorcycle": (0, 0, 255)                   # أحمر (مخالفة مرور)
        }

    def apply_preprocessing_filters(self, frame):
        """
        مرحلة التجهيز: تطبيق فلاتر معالجة مسبقة لإزالة الضوضاء وتحسين الرؤية ديناميكياً
        """
        # 1. إزالة الضوضاء (Noise Reduction)
        blur = cv2.GaussianBlur(frame, (3, 3), 0)

        # 2. تحسين مرونة التباين والإضاءة عبر معالجة هيستوغرام قناة الإضاءة (Y)
        ycrcb = cv2.cvtColor(blur, cv2.COLOR_BGR2YCrCb)
        channels = list(cv2.split(ycrcb))
        channels[0] = cv2.equalizeHist(channels[0])
        ycrcb = cv2.merge(channels)
        
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    def track(self, source, on_frame=None):
        results = self.model.track(
            source=source,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.25, 
            imgsz=640,
            stream=True,
            verbose=False
        )

        for r in results:
            orig_frame = r.orig_img
            orig_h, orig_w = orig_frame.shape[:2]
            
            # أبعاد العرض الآمنة داخل الواجهة لمنع استهلاك الموارد وبطء الـ FPS
            target_w, target_h = 800, 500
            resized_frame = cv2.resize(orig_frame, (target_w, target_h))
            current_time = time.time()

            # تمرير الصورة عبر الفلاتر قبل الرسم
            annotated_frame = self.apply_preprocessing_filters(resized_frame)

            # خط العد الأفقي (25% من أسفل الإطار)
            counting_line_y = int(target_h * 0.75)

            # الخط المنصف العمودي لتحديد اتجاه السير (ذهاب / إياب)
            center_line_x = int(target_w * 0.50)

            if r.boxes is not None and r.boxes.id is not None:
                box_xyxy = r.boxes.xyxy.cpu().numpy()
                box_ids = r.boxes.id.cpu().numpy().astype(int)
                box_clss = r.boxes.cls.cpu().numpy().astype(int)

                for i in range(len(box_ids)):
                    track_id = int(box_ids[i])
                    class_id = int(box_clss[i])
                    
                    raw_class_name = self.model.names[class_id]

                    # استخراج وتعديل معايرة الإحداثيات لتتطابق مع أبعاد الـ Resize الجديدة بدقة
                    orig_x1, orig_y1, orig_x2, orig_y2 = box_xyxy[i]
                    x1 = int(orig_x1 * (target_w / orig_w))
                    x2 = int(orig_x2 * (target_w / orig_w))
                    y1 = int(orig_y1 * (target_h / orig_h))
                    y2 = int(orig_y2 * (target_h / orig_h))

                    box_width = x2 - x1
                    box_height = y2 - y1

                    # منطق توزيع وتصنيف الفئات المستقلة المذكورة بالتوصيف
                    if raw_class_name == "motorcycle":
                        # تفرقة الدراجة العادية عن شرطة المرور (يمكنك إدراج شرط لوني أو هيكلي حسب تدريبك)
                        class_name = "motorcycle"
                    elif raw_class_name == "car" and (box_width / box_height < 1.1 and box_height > 50):
                        class_name = "van"
                    elif raw_class_name in self.category_counts:
                        class_name = raw_class_name
                    else:
                        class_name = "car"

                    center_x = int((x1 + x2) / 2)
                    bottom_y = y2

                    # حساب السرعة الحركية التقريبية بكسل/ثانية
                    estimated_speed = 0.0
                    if track_id in self.speed_tracker:
                        prev_y, prev_time = self.speed_tracker[track_id]
                        time_elapsed = current_time - prev_time
                        if time_elapsed > 0:
                            estimated_speed = (abs(bottom_y - prev_y) / time_elapsed) * 0.25
                    
                    self.speed_tracker[track_id] = (bottom_y, current_time)

                    # فرز وتحديد المخالفات (مخالفة نوع دراجة عادية أو مخالفة سرعة زائدة)
                    is_type_violation = (class_name == "motorcycle")
                    is_speed_violation = (estimated_speed > self.speed_limit)
                    is_any_violation = is_type_violation or is_speed_violation

                    # تحديد جهة قدوم المركبة بناءً على موقعها الحالي من الخط المنصف
                    coming_direction = "نيمي" if center_x < center_line_x else "شمال"

                    # إرسال التنبيه الفوري الفوري المطلوب للشرطة في الكونسول عند الرصد الأول
                    if is_type_violation and track_id not in self.counted_ids:
                        print(f"هبتنا! مرور فلاخم قادم كيلا - {coming_direction}.")
                    elif is_speed_violation and track_id not in self.counted_ids:
                        print(f"رصد مخالفة سرعة! مركبة {class_name} قادمة من جهة - {coming_direction}.")

                    # التحقق من العبور الفعلي لخط العد لحساب الإحصائيات والرسوم
                    if track_id in self.previous_positions:
                        previous_y = self.previous_positions[track_id]
                        crossed_line = (
                            (previous_y < counting_line_y <= bottom_y) or
                            (previous_y > counting_line_y >= bottom_y)
                        )

                        if crossed_line and track_id not in self.counted_ids:
                            self.counted_ids.add(track_id)
                            self.total_count += 1
                            self.category_counts[class_name] += 1
                            self.total_revenue += self.rates[class_name]

                            if center_x < center_line_x:
                                self.going_count += 1
                            else:
                                self.returning_count += 1

                    self.previous_positions[track_id] = bottom_y

                    # تطبيق التلوين المخصص (حجز اللون الأحمر حصرياً للمخالفات)
                    box_color = (0, 0, 255) if is_any_violation else self.colors.get(class_name, (255, 255, 0))
                    
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
                    
                    status_tag = " [SPEED OVER]" if is_speed_violation else (" [ILLEGAL]" if is_type_violation else "")
                    label_text = f"{class_name.upper()} ID:{track_id} {int(estimated_speed)}km/h{status_tag}"
                    cv2.putText(annotated_frame, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 2)

            # رسم خط العد والخط المنصف على شاشة العرض
            cv2.line(annotated_frame, (0, counting_line_y), (target_w, counting_line_y), (255, 255, 0), 3)
            cv2.line(annotated_frame, (center_line_x, 0), (center_line_x, target_h), (0, 255, 255), 3)

            # تعبئة وتغذية الإحصائيات بالوقت الحقيقي لإرسالها للـ GUI
            stats = {
                "total": self.total_count,
                "going": self.going_count,
                "returning": self.returning_count,
                "revenue": self.total_revenue,
                "cars": self.category_counts["car"],
                "vans": self.category_counts["van"],
                "buses": self.category_counts["bus"],
                "trucks": self.category_counts["truck"],
                "motorcycles": self.category_counts["motorcycle"],
                "police_motorcycles": self.category_counts["traffic-police motorcycle"]
            }

            if on_frame:
                on_frame(annotated_frame, stats)

        # التقرير النهائي الإلزامي عند نهاية تشغيل الفيديو بالكامل
        print("\n" + "="*50 + "\n--- التقرير النهائي لنظام المرور الذكي ---")
        print(f"العدد الإجمالي للمركبات: {self.total_count}")
        print(f"إجمالي حركة الذهاب: {self.going_count} | إجمالي حركة الإياب: {self.returning_count}")
        print(f"مجموع الدخل الكلي المحصل: ${self.total_revenue:.2f}")
        print("الأعداد التفصيلية بحسب الفئات:")
        for category, count in self.category_counts.items():
            print(f" - {category}: {count}")
        print("="*50)
