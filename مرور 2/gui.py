import customtkinter as ctk
from tkinter import filedialog
import threading
from PIL import Image

class TrafficGUI:

    def __init__(self, on_start):
        self.video_path = None
        self.on_start = on_start
        self.running = False

        self.root = ctk.CTk()
        self.root.title("Traffic Monitoring System")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 650)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Header Frame
        self.header = ctk.CTkFrame(self.root, corner_radius=15)
        self.header.pack(fill="x", padx=20, pady=(20, 10))

        self.title = ctk.CTkLabel(self.header, text="TRAFFIC MONITORING SYSTEM", font=("Arial", 26, "bold"))
        self.title.pack(side="left", padx=20, pady=15)

        self.status = ctk.CTkLabel(self.header, text="● OFFLINE", text_color="red", font=("Arial", 16, "bold"))
        self.status.pack(side="right", padx=20)

        # Content Frame
        self.content = ctk.CTkFrame(self.root, corner_radius=15)
        self.content.pack(fill="both", expand=True, padx=20, pady=10)

        # Video Section
        self.video_frame = ctk.CTkFrame(self.content, corner_radius=15)
        self.video_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.video_title = ctk.CTkLabel(self.video_frame, text="VIDEO PREVIEW", font=("Arial", 20, "bold"))
        self.video_title.pack(pady=15)

        self.video_area = ctk.CTkLabel(self.video_frame, text="No video selected", font=("Arial", 22))
        self.video_area.pack(fill="both", expand=True, padx=20, pady=20)

        # Side Statistics Panel
        self.stats_frame = ctk.CTkFrame(self.content, width=280, corner_radius=15)
        self.stats_frame.pack(side="right", fill="y", padx=10, pady=10)
        self.stats_frame.pack_propagate(False)

        self.stats_title = ctk.CTkLabel(self.stats_frame, text="LIVE STATISTICS", font=("Arial", 19, "bold"))
        self.stats_title.pack(pady=20)

        # هيكلة وعرض الفئات الستة المطلوبة بالتفصيل في لوحة العرض الجانبية
        self.stat_labels = {}
        self.create_stat("Cars", "0")
        self.create_stat("Vans", "0")
        self.create_stat("Buses", "0")
        self.create_stat("Trucks", "0")
        self.create_stat("Motorcycles", "0")
        self.create_stat("Police Moto", "0")

        self.total_label = ctk.CTkLabel(self.stats_frame, text="TOTAL VEHICLES\n0", font=("Arial", 19, "bold"))
        self.total_label.pack(pady=15)

        self.going_label = ctk.CTkLabel(self.stats_frame, text="GOING\n0", font=("Arial", 17, "bold"))
        self.going_label.pack(pady=8)

        self.returning_label = ctk.CTkLabel(self.stats_frame, text="RETURNING\n0", font=("Arial", 17, "bold"))
        self.returning_label.pack(pady=8)

        self.revenue_label = ctk.CTkLabel(self.stats_frame, text="REVENUE\n$0.00", font=("Arial", 19, "bold"))
        self.revenue_label.pack(pady=15)

        # Control Area
        self.controls = ctk.CTkFrame(self.root, corner_radius=15)
        self.controls.pack(fill="x", padx=20, pady=(10, 20))

        self.select_button = ctk.CTkButton(self.controls, text="Select Video", width=150, height=40, command=self.select_video)
        self.select_button.pack(side="left", padx=10, pady=15)

        self.start_button = ctk.CTkButton(self.controls, text="▶  START", width=150, height=40, command=self.start)
        self.start_button.pack(side="left", padx=10)

        self.stop_button = ctk.CTkButton(self.controls, text="■  STOP", width=150, height=40, command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=10)

        self.progress_label = ctk.CTkLabel(self.controls, text="", font=("Arial", 14))
        self.progress_label.pack(side="right", padx=20)

    def create_stat(self, name, value):
        label = ctk.CTkLabel(self.stats_frame, text=f"{name}:  {value}", font=("Arial", 16))
        label.pack(anchor="w", padx=30, pady=5)
        self.stat_labels[name] = label

    def select_video(self):
        self.video_path = filedialog.askopenfilename(
            title="Select Traffic Video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if self.video_path:
            self.video_area.configure(text=f"Selected:\n{self.video_path}", image=None)
            self.status.configure(text="● READY", text_color="orange")

    def start(self):
        if not self.video_path:
            self.status.configure(text="● NO VIDEO", text_color="red")
            self.progress_label.configure(text="Select a video first")
            return

        if self.running:
            return

        self.running = True
        self.status.configure(text="● RUNNING", text_color="green")
        self.progress_label.configure(text="Processing...")
        self.select_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        thread = threading.Thread(target=self.run_tracking, daemon=True)
        thread.start()

    def run_tracking(self):
        try:
            self.on_start(self.video_path, self.update_frame)
            self.root.after(0, self.processing_done)
        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda: self.processing_error(error_message))

    def update_frame(self, frame, stats):
        if not self.running:
            return
        self.root.after(0, lambda: self.display_frame(frame, stats))

    def display_frame(self, frame, stats):
        # تحديث لوحة العرض والمجاميع الكلية بالوقت الحقيقي
        self.total_label.configure(text=f"TOTAL VEHICLES\n{stats['total']}")
        self.going_label.configure(text=f"GOING\n{stats['going']}")
        self.returning_label.configure(text=f"RETURNING\n{stats['returning']}")
        self.revenue_label.configure(text=f"REVENUE\n${stats['revenue']:.2f}")

        # تحديث عدادات الفئات الفرعية الحية الستة
        self.stat_labels["Cars"].configure(text=f"Cars:  {stats['cars']}")
        self.stat_labels["Vans"].configure(text=f"Vans:  {stats['vans']}")
        self.stat_labels["Buses"].configure(text=f"Buses:  {stats['buses']}")
        self.stat_labels["Trucks"].configure(text=f"Trucks:  {stats['trucks']}")
        self.stat_labels["Motorcycles"].configure(text=f"Motorcycles:  {stats['motorcycles']}")
        self.stat_labels["Police Moto"].configure(text=f"Police Moto:  {stats['police_motorcycles']}")

        # تحويل قنوات الألوان وتحديث الفريم المعروض
        frame_rgb = frame[:, :, ::-1]
        image = Image.fromarray(frame_rgb)

        width = self.video_area.winfo_width()
        height = self.video_area.winfo_height()

        if width <= 1 or height <= 1:
            width = 800
            height = 500

        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.video_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.video_area.configure(image=self.video_image, text="")

    def processing_done(self):
        self.running = False
        self.status.configure(text="● DONE ✓", text_color="green")
        self.progress_label.configure(text="Processing completed")
        self.start_button.configure(state="normal")
        self.select_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def processing_error(self, error):
        self.running = False
        self.status.configure(text="● ERROR", text_color="red")
        self.progress_label.configure(text="Processing failed")
        print("Error:", error)
        self.start_button.configure(state="normal")
        self.select_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def stop(self):
        self.running = False
        self.status.configure(text="● STOPPED", text_color="red")
        self.progress_label.configure(text="Stopped")

    def run(self):
        self.root.mainloop()
