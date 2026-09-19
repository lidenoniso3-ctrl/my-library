# -*- coding: utf-8 -*-
"""
PixelForge AI v4.0 — Professional Image Converter & Enhancer (single file)
• Batch conversion of an entire folder
• WebP / AVIF with full compression control
• Multi-layer enhancement engine — no PyTorch or external models
"""

import os
import sys
import threading
import queue
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, messagebox, colorchooser

import customtkinter as ctk
from PIL import Image, ImageFilter, ImageEnhance, ImageChops

# ---------- Optional components ----------
try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pillow_avif  # noqa
    AVIF_AVAILABLE = True
except ImportError:
    AVIF_AVAILABLE = False

# DPI awareness (Windows only, safely ignored elsewhere)
try:
    if sys.platform.startswith("win"):
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


# ============================================================
#                      Configuration
# ============================================================
APP_NAME = "PixelForge AI"
APP_VERSION = "4.0"

FORMATS = {
    "PNG":  {"ext": ".png",  "alpha": True,  "quality": False, "available": True},
    "JPEG": {"ext": ".jpg",  "alpha": False, "quality": True,  "available": True},
    "WEBP": {"ext": ".webp", "alpha": True,  "quality": True,  "available": True},
    "AVIF": {"ext": ".avif", "alpha": True,  "quality": True,  "available": AVIF_AVAILABLE},
    "BMP":  {"ext": ".bmp",  "alpha": False, "quality": False, "available": True},
    "TIFF": {"ext": ".tif",  "alpha": True,  "quality": False, "available": True},
    "GIF":  {"ext": ".gif",  "alpha": False, "quality": False, "available": True},
    "ICO":  {"ext": ".ico",  "alpha": True,  "quality": False, "available": True},
    "PDF":  {"ext": ".pdf",  "alpha": False, "quality": False, "available": True},
    "PPM":  {"ext": ".ppm",  "alpha": False, "quality": False, "available": True},
}

INPUT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
              ".gif", ".ico", ".ppm", ".pbm", ".pgm", ".jfif", ".avif"}

ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"
SUCCESS = "#10B981"
ERROR = "#EF4444"
WARNING = "#F59E0B"


# ============================================================
#           Advanced Enhancement Engine — no models
# ============================================================
class SmartEnhancer:
    """
    Multi-layer enhancement engine built entirely on PIL + NumPy + OpenCV.
    Emulates neural-network behavior via a combination of:
    1) Edge-preserving denoise
    2) Progressive multi-step upscaling
    3) Fine-detail boost
    4) Local contrast correction
    5) Adaptive sharpening based on edge density
    6) Adaptive blending between original and result
    """

    # ---------- 1) Edge-preserving denoise ----------
    @staticmethod
    def _denoise_pil(img):
        """PIL fallback for edge-preserving denoise."""
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = img.filter(ImageFilter.SMOOTH)
        return img

    @staticmethod
    def _denoise_cv(img, d=7, sc=50, ss=50):
        """Bilateral Filter — best for preserving edges."""
        if not CV2_AVAILABLE or not NP_AVAILABLE:
            return SmartEnhancer._denoise_pil(img)
        arr = np.array(img.convert("RGB"))
        result = cv2.bilateralFilter(arr, d, sc, ss)
        return Image.fromarray(result)

    # ---------- 2) Progressive upscale ----------
    @staticmethod
    def _progressive_upscale(img, factor):
        """Multi-step upscaling for cleaner results."""
        if factor <= 1.0:
            return img
        result = img
        remaining = factor
        while remaining > 1.01:
            step = min(2.0, remaining)
            new_size = (max(1, int(result.width * step)),
                        max(1, int(result.height * step)))
            result = result.resize(new_size, Image.LANCZOS)
            remaining /= step
        fw = max(1, int(img.width * factor))
        fh = max(1, int(img.height * factor))
        if result.size != (fw, fh):
            result = result.resize((fw, fh), Image.LANCZOS)
        return result

    # ---------- 3) Detail boost ----------
    @staticmethod
    def _detail_boost_pil(img, strength=0.35):
        """Boost details via difference between original and smoothed."""
        smooth = img.filter(ImageFilter.GaussianBlur(radius=2))
        diff = ImageChops.difference(img.convert("RGB"), smooth.convert("RGB"))
        return Image.blend(img.convert("RGB"), diff, alpha=strength)

    @staticmethod
    def _detail_boost_cv(img):
        """cv2.detailEnhance — faster and better."""
        if not CV2_AVAILABLE or not NP_AVAILABLE:
            return img
        arr = np.array(img.convert("RGB"))
        result = cv2.detailEnhance(arr, sigma_s=10, sigma_r=0.15)
        return Image.fromarray(result)

    # ---------- 4) Local contrast ----------
    @staticmethod
    def _local_contrast_pil(img, amount=1.10):
        """PIL fallback for CLAHE — overall contrast boost."""
        return ImageEnhance.Contrast(img).enhance(amount)

    @staticmethod
    def _local_contrast_cv(img, clip=1.8, grid=8):
        """CLAHE — local contrast enhancement."""
        if not CV2_AVAILABLE or not NP_AVAILABLE:
            return SmartEnhancer._local_contrast_pil(img)
        arr = np.array(img.convert("RGB"))
        lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
        l = clahe.apply(l)
        merged = cv2.merge([l, a, b])
        return Image.fromarray(cv2.cvtColor(merged, cv2.COLOR_LAB2RGB))

    # ---------- 5) Adaptive sharpening ----------
    @staticmethod
    def _adaptive_sharpen(img, strength=3):
        """
        Multi-layer Unsharp Mask:
        - coarse layer for clear edges
        - fine layer for small details
        """
        percent1 = 80 + strength * 35
        radius1 = 1.5 + strength * 0.2
        img1 = img.filter(ImageFilter.UnsharpMask(
            radius=radius1, percent=percent1, threshold=3))

        percent2 = 40 + strength * 20
        radius2 = 0.8
        img2 = img1.filter(ImageFilter.UnsharpMask(
            radius=radius2, percent=percent2, threshold=2))

        return img2

    # ---------- 6) Adaptive blend ----------
    @staticmethod
    def _adaptive_blend(original, enhanced, upscaled, alpha=0.85):
        """Blend pure Bicubic with enhanced result to reduce halos."""
        return Image.blend(upscaled, enhanced, alpha=alpha)

    # ---------- Main pipeline ----------
    @classmethod
    def enhance(cls, img, scale=2.0, sharpness=3,
                denoise=True, progress_cb=None):
        """Full enhancement pipeline."""
        original_mode = img.mode
        work = img.convert("RGB") if img.mode not in ("RGB", "L") else img

        # 1) Denoise
        if denoise:
            if progress_cb: progress_cb("Edge-preserving denoise...")
            work = cls._denoise_cv(work)

        # 2) Upscale
        if scale > 1.0:
            if progress_cb: progress_cb(f"Progressive upscale {scale}x...")
            upscaled = cls._progressive_upscale(work, scale)
        else:
            upscaled = work

        # 3) Detail boost
        if scale > 1.0:
            if progress_cb: progress_cb("Boosting details...")
            enhanced = cls._detail_boost_cv(upscaled)
        else:
            enhanced = upscaled

        # 4) Local contrast
        if progress_cb: progress_cb("Enhancing local contrast...")
        enhanced = cls._local_contrast_cv(enhanced, clip=1.8)

        # 5) Adaptive sharpen
        if progress_cb: progress_cb("Adaptive sharpening...")
        enhanced = cls._adaptive_sharpen(enhanced, strength=sharpness)

        # 6) Adaptive blend
        if scale > 1.0:
            if progress_cb: progress_cb("Final adaptive blend...")
            result = cls._adaptive_blend(work, enhanced, upscaled, alpha=0.88)
        else:
            result = enhanced

        # Restore alpha
        if original_mode in ("RGBA", "LA", "P") and img.mode in ("RGBA", "LA", "P"):
            alpha = img.convert("RGBA").split()[-1]
            alpha = alpha.resize(result.size, Image.LANCZOS)
            result = result.convert("RGBA")
            result.putalpha(alpha)

        return result


# ============================================================
#                       Application
# ============================================================
class PixelForgeAI(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1320x860")
        self.minsize(1120, 740)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.source_folder = None
        self.output_folder = None
        self.image_files = []
        self.bg_color_value = "#FFFFFF"
        self.is_running = False
        self.cancel_flag = threading.Event()
        self.msg_queue = queue.Queue()
        self.stats = {"done": 0, "failed": 0}
        self.start_time = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=440)
        self.grid_columnconfigure(1, weight=1)

        self._build_header()
        self._build_settings()
        self._build_progress()
        self._on_format_change(self.format_var.get())
        self._poll_queue()

        # Optional components notice
        if not AVIF_AVAILABLE:
            self._log("⚠️ pillow-avif-plugin not installed — AVIF disabled.", "warn")
        if not CV2_AVAILABLE:
            self._log("ℹ️ OpenCV not installed — Smart mode runs in PIL-only mode.", "info")
        if not NP_AVAILABLE:
            self._log("ℹ️ NumPy not installed — enhancement runs in basic PIL mode.", "info")

    # --------------------------------------------------------
    def _build_header(self):
        h = ctk.CTkFrame(self, height=72, corner_radius=0,
                         fg_color=("gray88", "gray10"))
        h.grid(row=0, column=0, columnspan=2, sticky="ew")
        h.grid_propagate(False)
        h.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(h, text=f"  🎨  {APP_NAME}",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=(ACCENT, "#60A5FA")).grid(
            row=0, column=0, padx=(16, 0), pady=16, sticky="w")

        ctk.CTkLabel(h,
                     text="Batch conversion • WebP/AVIF • Multi-layer smart enhancement",
                     font=ctk.CTkFont(size=12),
                     text_color=("gray40", "gray60")).grid(
            row=0, column=1, padx=12, pady=16, sticky="w")

        self.theme_switch = ctk.CTkSwitch(
            h, text="Dark",
            command=lambda: ctk.set_appearance_mode(
                "Dark" if self.theme_switch.get() else "Light"))
        self.theme_switch.select()
        self.theme_switch.grid(row=0, column=2, padx=16, pady=16, sticky="e")

    # --------------------------------------------------------
    def _section(self, parent, title):
        f = ctk.CTkFrame(parent, corner_radius=12,
                         fg_color=("gray86", "gray17"))
        f.pack(fill="x", padx=14, pady=(14, 0))
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(12, 8))
        return f

    def _build_settings(self):
        panel = ctk.CTkScrollableFrame(self, corner_radius=0,
                                       fg_color=("gray92", "gray13"))
        panel.grid(row=1, column=0, sticky="nsew")

        # ---------- Folders ----------
        sec = self._section(panel, "📁  Folders")
        ctk.CTkLabel(sec, text="Source folder:", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("gray25", "gray75")).pack(fill="x", padx=14)
        self.src_label = ctk.CTkLabel(sec, text="— Not selected —",
                                      anchor="w", font=ctk.CTkFont(size=11),
                                      text_color=("gray45", "gray55"),
                                      wraplength=380)
        self.src_label.pack(fill="x", padx=14, pady=(2, 6))
        ctk.CTkButton(sec, text="📂  Select Source Folder", height=38,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._pick_source).pack(
            fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(sec, text="Output folder:", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("gray25", "gray75")).pack(fill="x", padx=14)
        self.out_label = ctk.CTkLabel(sec, text="— Not selected —",
                                      anchor="w", font=ctk.CTkFont(size=11),
                                      text_color=("gray45", "gray55"),
                                      wraplength=380)
        self.out_label.pack(fill="x", padx=14, pady=(2, 6))
        ctk.CTkButton(sec, text="📂  Select Output Folder", height=38,
                      fg_color=("gray75", "gray25"),
                      hover_color=("gray65", "gray32"),
                      text_color=("gray10", "gray90"),
                      command=self._pick_output).pack(
            fill="x", padx=14, pady=(0, 10))

        self.same_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sec, text="Use '_converted' subfolder",
                        variable=self.same_folder_var,
                        font=ctk.CTkFont(size=11),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 6))

        self.recursive_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sec, text="Include subfolders",
                        variable=self.recursive_var,
                        font=ctk.CTkFont(size=11),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 4))

        self.keep_structure_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sec, text="Preserve folder structure",
                        variable=self.keep_structure_var,
                        font=ctk.CTkFont(size=11),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 14))

        # ---------- Output format ----------
        sec = self._section(panel, "📄  Output Format & Compression")
        avail = [k for k, v in FORMATS.items() if v["available"]]
        self.format_var = ctk.StringVar(value="WEBP")
        ctk.CTkOptionMenu(sec, values=avail, variable=self.format_var,
                          command=self._on_format_change, height=38,
                          font=ctk.CTkFont(size=13)).pack(
            fill="x", padx=14, pady=(0, 10))

        self.quality_label = ctk.CTkLabel(sec, text="Quality: 85", anchor="w",
                                          font=ctk.CTkFont(size=12))
        self.quality_label.pack(fill="x", padx=14)
        self.quality_slider = ctk.CTkSlider(
            sec, from_=1, to=100, number_of_steps=99,
            command=lambda v: self.quality_label.configure(
                text=f"Quality: {int(v)}"),
            button_color=ACCENT, progress_color=ACCENT)
        self.quality_slider.set(85)
        self.quality_slider.pack(fill="x", padx=14, pady=(0, 8))

        self.lossless_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sec, text="Lossless compression",
                        variable=self.lossless_var, font=ctk.CTkFont(size=11),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 14))

        # ---------- Dimensions ----------
        sec = self._section(panel, "📐  Dimensions")
        self.resize_mode = ctk.StringVar(value="Original")
        ctk.CTkSegmentedButton(
            sec, values=["Original", "Percent %", "Custom"],
            variable=self.resize_mode, command=self._on_resize_mode,
            height=34, font=ctk.CTkFont(size=12),
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER).pack(
            fill="x", padx=14, pady=(0, 12))

        self.percent_frame = ctk.CTkFrame(sec, fg_color="transparent")
        self.percent_label = ctk.CTkLabel(self.percent_frame,
                                          text="Percent: 100%", anchor="w",
                                          font=ctk.CTkFont(size=12))
        self.percent_label.pack(fill="x")
        self.percent_slider = ctk.CTkSlider(
            self.percent_frame, from_=1, to=300, number_of_steps=299,
            command=lambda v: self.percent_label.configure(
                text=f"Percent: {int(v)}%"),
            button_color=ACCENT, progress_color=ACCENT)
        self.percent_slider.set(100)
        self.percent_slider.pack(fill="x", pady=(0, 4))

        self.custom_frame = ctk.CTkFrame(sec, fg_color="transparent")
        wh = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        wh.pack(fill="x")
        wh.grid_columnconfigure((0, 2), weight=1)
        ctk.CTkLabel(wh, text="Width",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(wh, text="Height",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=2,
                                                     sticky="w", padx=(10, 0))
        self.width_entry = ctk.CTkEntry(wh, height=34, justify="center",
                                        placeholder_text="1920")
        self.width_entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        ctk.CTkLabel(wh, text="✕").grid(row=1, column=1, padx=8)
        self.height_entry = ctk.CTkEntry(wh, height=34, justify="center",
                                         placeholder_text="1080")
        self.height_entry.grid(row=1, column=2, sticky="ew", pady=(2, 0))

        # ---------- Smart enhancement ----------
        sec = self._section(panel, "🧠  Smart Enhancement & Upscaling")

        ctk.CTkLabel(
            sec,
            text="Multi-layer engine — no models, no downloads\n"
                 "(denoise → progressive upscale → detail → contrast → sharpen)",
            font=ctk.CTkFont(size=10), text_color=("gray45", "gray55"),
            anchor="w", justify="left", wraplength=380).pack(
            fill="x", padx=14, pady=(0, 8))

        self.ai_enable_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sec, text="Enable Smart Enhancement",
                        variable=self.ai_enable_var, font=ctk.CTkFont(size=12),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 8))

        ctk.CTkLabel(sec, text="Upscale factor:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=14)
        self.ai_scale_var = ctk.StringVar(value="2x")
        ctk.CTkOptionMenu(sec, values=["1x", "1.5x", "2x", "3x", "4x"],
                          variable=self.ai_scale_var, height=34,
                          font=ctk.CTkFont(size=12)).pack(
            fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(sec, text="Sharpness intensity (1-5):", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=14)
        self.sharp_slider = ctk.CTkSlider(
            sec, from_=1, to=5, number_of_steps=4,
            button_color=ACCENT, progress_color=ACCENT)
        self.sharp_slider.set(3)
        self.sharp_slider.pack(fill="x", padx=14, pady=(2, 8))

        self.denoise_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sec, text="Denoise before upscaling",
                        variable=self.denoise_var, font=ctk.CTkFont(size=11),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 8))

        # Engine note
        engine_txt = "⚡ Current mode: "
        if CV2_AVAILABLE and NP_AVAILABLE:
            engine_txt += "Full (OpenCV + NumPy)"
        elif NP_AVAILABLE:
            engine_txt += "Medium (NumPy only)"
        else:
            engine_txt += "Basic (PIL only)"

        ctk.CTkLabel(sec, text=engine_txt,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=(ACCENT, "#60A5FA"),
                     anchor="w", wraplength=380).pack(
            fill="x", padx=14, pady=(0, 14))

        # ---------- Background ----------
        sec = self._section(panel, "🎨  Transparency Background")
        ctk.CTkLabel(sec, text="For formats that don't support alpha",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray40", "gray60"),
                     anchor="w", wraplength=380).pack(
            fill="x", padx=14, pady=(0, 8))
        self.bg_btn = ctk.CTkButton(
            sec, text=self.bg_color_value, height=38,
            fg_color=self.bg_color_value, text_color="#000000",
            hover_color=self.bg_color_value,
            border_width=1, border_color=("gray60", "gray40"),
            command=self._pick_bg, font=ctk.CTkFont(size=12, weight="bold"))
        self.bg_btn.pack(fill="x", padx=14, pady=(0, 14))

        # ---------- Advanced ----------
        sec = self._section(panel, "⚙️  Advanced Options")
        self.overwrite_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sec, text="Overwrite existing files",
                        variable=self.overwrite_var, font=ctk.CTkFont(size=12),
                        checkbox_width=18, checkbox_height=18,
                        fg_color=ACCENT).pack(anchor="w", padx=14, pady=(0, 14))

        self._on_resize_mode("Original")

    # --------------------------------------------------------
    def _build_progress(self):
        panel = ctk.CTkFrame(self, corner_radius=0,
                             fg_color=("gray96", "gray10"))
        panel.grid(row=1, column=1, sticky="nsew")
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        stats = ctk.CTkFrame(panel, corner_radius=14,
                             fg_color=("gray88", "gray15"))
        stats.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        stats.grid_columnconfigure((0, 1, 2), weight=1)
        self.stat_total = self._stat_card(stats, "Total", "0",
                                          ("gray25", "gray85"), 0)
        self.stat_done = self._stat_card(stats, "Success", "0", SUCCESS, 1)
        self.stat_fail = self._stat_card(stats, "Failed", "0", ERROR, 2)

        prog = ctk.CTkFrame(panel, corner_radius=14,
                            fg_color=("gray88", "gray15"))
        prog.grid(row=1, column=0, sticky="ew", padx=20, pady=8)

        top = ctk.CTkFrame(prog, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 6))
        self.status_label = ctk.CTkLabel(top, text="⏸️  Idle",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         anchor="w")
        self.status_label.pack(side="left")
        self.percent_label = ctk.CTkLabel(top, text="0%",
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          text_color=ACCENT, anchor="e")
        self.percent_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(prog, height=14,
                                               corner_radius=7,
                                               progress_color=ACCENT)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 8))

        self.current_label = ctk.CTkLabel(prog, text="—", anchor="w",
                                          font=ctk.CTkFont(size=11),
                                          text_color=("gray40", "gray60"))
        self.current_label.pack(fill="x", padx=16, pady=(0, 14))

        btns = ctk.CTkFrame(prog, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(0, 16))
        btns.grid_columnconfigure((0, 1, 2), weight=1)

        self.scan_btn = ctk.CTkButton(
            btns, text="🔍  Scan", height=44,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray32"),
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._scan)
        self.scan_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.start_btn = ctk.CTkButton(
            btns, text="🚀  Start Conversion", height=44,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start)
        self.start_btn.grid(row=0, column=1, sticky="ew", padx=6)

        self.cancel_btn = ctk.CTkButton(
            btns, text="✕  Cancel", height=44,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray32"),
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled", command=self._cancel)
        self.cancel_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        log_frame = ctk.CTkFrame(panel, corner_radius=14,
                                 fg_color=("gray88", "gray15"))
        log_frame.grid(row=2, column=0, sticky="nsew",
                       padx=20, pady=(8, 20))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        lh = ctk.CTkFrame(log_frame, fg_color="transparent")
        lh.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        lh.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lh, text="📋  Log",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(lh, text="Clear", width=70, height=26,
                      fg_color="transparent",
                      hover_color=("gray75", "gray25"),
                      text_color=("gray35", "gray70"),
                      font=ctk.CTkFont(size=11),
                      command=self._clear_log).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(
            log_frame, corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("gray95", "gray12"),
            text_color=("gray15", "gray85"), wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew",
                          padx=16, pady=(0, 14))
        self.log_box.configure(state="disabled")

    def _stat_card(self, parent, title, value, color, col):
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color="transparent")
        card.grid(row=0, column=col, sticky="ew", padx=6, pady=12)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11),
                     text_color=("gray45", "gray55")).pack(pady=(4, 0))
        lbl = ctk.CTkLabel(card, text=value,
                           font=ctk.CTkFont(size=24, weight="bold"),
                           text_color=color)
        lbl.pack(pady=(0, 6))
        return lbl

    # --------------------------------------------------------
    def _pick_source(self):
        f = filedialog.askdirectory(title="Select images folder")
        if f:
            self.source_folder = f
            self.src_label.configure(text=f, text_color=(ACCENT, "#60A5FA"))
            self._scan()

    def _pick_output(self):
        f = filedialog.askdirectory(title="Select output folder")
        if f:
            self.output_folder = f
            self.out_label.configure(text=f, text_color=(ACCENT, "#60A5FA"))

    def _pick_bg(self):
        c = colorchooser.askcolor(color=self.bg_color_value, title="Background color")
        if c and c[1]:
            self.bg_color_value = c[1]
            r, g, b = (int(c[1][i:i+2], 16) for i in (1, 3, 5))
            lum = 0.299*r + 0.587*g + 0.114*b
            txt = "#000000" if lum > 140 else "#FFFFFF"
            self.bg_btn.configure(text=c[1], fg_color=c[1],
                                  hover_color=c[1], text_color=txt)

    def _scan(self):
        if not self.source_folder:
            messagebox.showwarning("Warning", "Please select a source folder.")
            return
        root = Path(self.source_folder)
        it = root.rglob("*") if self.recursive_var.get() else root.glob("*")
        files = []
        for p in it:
            try:
                if p.is_file() and p.suffix.lower() in INPUT_EXTS:
                    files.append(p)
            except Exception:
                continue
        self.image_files = sorted(files)
        self.stat_total.configure(text=str(len(self.image_files)))
        if not self.image_files:
            self._log("⚠️ No images found.", "warn")
        else:
            self._log(f"✅ {len(self.image_files)} images ready.", "success")
            self.status_label.configure(text="✅ Ready")

    def _start(self):
        if self.is_running:
            return
        if not self.source_folder:
            messagebox.showwarning("Warning", "Please select a source folder.")
            return
        if not self.image_files:
            self._scan()
            if not self.image_files:
                return
        if self.same_folder_var.get():
            self.output_folder = str(Path(self.source_folder) / "_converted")
        if not self.output_folder:
            messagebox.showwarning("Warning", "Please select an output folder.")
            return
        try:
            Path(self.output_folder).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self.stats = {"done": 0, "failed": 0}
        self.stat_done.configure(text="0")
        self.stat_fail.configure(text="0")
        self.progress_bar.set(0)
        self.percent_label.configure(text="0%")

        try:
            ai_scale = float(self.ai_scale_var.get().replace("x", ""))
        except ValueError:
            ai_scale = 2.0

        cfg = {
            "format": self.format_var.get(),
            "quality": int(self.quality_slider.get()),
            "lossless": self.lossless_var.get(),
            "resize_mode": self.resize_mode.get(),
            "percent": float(self.percent_slider.get()),
            "width": self.width_entry.get().strip(),
            "height": self.height_entry.get().strip(),
            "bg_color": self.bg_color_value,
            "overwrite": self.overwrite_var.get(),
            "keep_structure": self.keep_structure_var.get(),
            "recursive": self.recursive_var.get(),
            "ai_enable": self.ai_enable_var.get(),
            "ai_scale": ai_scale,
            "ai_sharp": int(self.sharp_slider.get()),
            "ai_denoise": self.denoise_var.get(),
        }

        self.cancel_flag.clear()
        self.is_running = True
        self.start_time = datetime.now()

        self.start_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status_label.configure(text="⚙️  Converting...")

        self._log("=" * 55, "info")
        mode = f" + enhance {cfg['ai_scale']}x" if cfg["ai_enable"] else ""
        self._log(f"🚀 {len(self.image_files)} images → {cfg['format']}{mode}",
                  "info")
        self._log("=" * 55, "info")

        threading.Thread(target=self._worker,
                         args=(list(self.image_files), cfg),
                         daemon=True).start()

    def _worker(self, files, cfg):
        fmt = cfg["format"]
        info = FORMATS[fmt]
        src_root = Path(self.source_folder)
        out_root = Path(self.output_folder)

        cw = ch = None
        if cfg["resize_mode"] == "Custom":
            try:
                cw = int(cfg["width"]) if cfg["width"] else None
                ch = int(cfg["height"]) if cfg["height"] else None
            except ValueError:
                pass

        total = len(files)
        for idx, src in enumerate(files, 1):
            if self.cancel_flag.is_set():
                self.msg_queue.put(("log", ("⛔ Cancelled.", "warn")))
                break
            src = Path(src)
            try:
                # Output path
                if cfg["keep_structure"] and cfg["recursive"]:
                    try:
                        rel = src.relative_to(src_root).parent
                    except ValueError:
                        rel = Path("")
                    dst_dir = out_root / rel
                else:
                    dst_dir = out_root
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst = dst_dir / (src.stem + info["ext"])
                if dst.exists() and not cfg["overwrite"]:
                    base = dst.stem
                    i = 1
                    while dst.exists():
                        dst = dst_dir / f"{base}_{i}{info['ext']}"
                        i += 1

                img = Image.open(src)
                img.load()

                # Smart enhancement
                if cfg["ai_enable"]:
                    def cb(m):
                        self.msg_queue.put(("status", f"🧠 {src.name}: {m}"))
                    try:
                        img = SmartEnhancer.enhance(
                            img, scale=cfg["ai_scale"],
                            sharpness=cfg["ai_sharp"],
                            denoise=cfg["ai_denoise"],
                            progress_cb=cb)
                    except Exception as e:
                        self.msg_queue.put(("log",
                            (f"⚠️ Enhancement failed on {src.name}: {e}", "warn")))

                # Dimensions
                img = self._apply_resize(img, cfg, cw, ch)

                # Transparency
                img = self._prepare(img, fmt, cfg["bg_color"])

                # Save
                kw = {}
                if info["quality"]:
                    kw["quality"] = cfg["quality"]
                    if fmt == "JPEG":
                        kw["optimize"] = True
                        kw["progressive"] = True
                    elif fmt == "WEBP":
                        kw["method"] = 6
                        if cfg["lossless"]:
                            kw["lossless"] = True
                    elif fmt == "AVIF":
                        if cfg["lossless"]:
                            kw["lossless"] = True

                if fmt == "ICO":
                    kw["sizes"] = [(256, 256), (128, 128), (64, 64),
                                   (48, 48), (32, 32), (16, 16)]
                    if img.width != img.height:
                        s = max(img.width, img.height)
                        canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
                        canvas.paste(img, ((s-img.width)//2, (s-img.height)//2))
                        img = canvas
                elif fmt == "PDF":
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    kw["resolution"] = 100.0
                elif fmt == "GIF":
                    if img.mode not in ("P", "L"):
                        img = img.convert("P", palette=Image.ADAPTIVE)

                img.save(dst, format=fmt, **kw)

                self.stats["done"] += 1
                self.msg_queue.put(("progress", {
                    "idx": idx, "total": total, "name": src.name,
                    "out": str(dst), "status": "done", "size": img.size}))

            except Exception as e:
                self.stats["failed"] += 1
                self.msg_queue.put(("progress", {
                    "idx": idx, "total": total, "name": src.name,
                    "out": "", "status": "error",
                    "error": f"{type(e).__name__}: {e}"}))

        self.msg_queue.put(("finished", None))

    @staticmethod
    def _apply_resize(img, cfg, cw, ch):
        m = cfg["resize_mode"]
        if m == "Original":
            return img
        if m == "Percent %":
            p = cfg["percent"]
            nw, nh = max(1, int(img.width*p/100)), max(1, int(img.height*p/100))
        else:
            if cw and ch:
                r = min(cw/img.width, ch/img.height)
                nw, nh = max(1, int(img.width*r)), max(1, int(img.height*r))
            elif cw:
                r = cw/img.width
                nw, nh = cw, max(1, int(img.height*r))
            elif ch:
                r = ch/img.height
                nw, nh = max(1, int(img.width*r)), ch
            else:
                return img
        if (nw, nh) == img.size:
            return img
        return img.resize((nw, nh), Image.LANCZOS)

    @staticmethod
    def _prepare(img, fmt, bg):
        info = FORMATS[fmt]
        if not info["alpha"]:
            has_a = (img.mode in ("RGBA", "LA")
                     or (img.mode == "P" and "transparency" in img.info))
            if has_a:
                rgba = img.convert("RGBA")
                b = Image.new("RGB", rgba.size, bg)
                b.paste(rgba, mask=rgba.split()[-1])
                img = b
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
        return img

    # --------------------------------------------------------
    def _poll_queue(self):
        try:
            while True:
                k, p = self.msg_queue.get_nowait()
                if k == "progress":
                    self._handle_progress(p)
                elif k == "log":
                    self._log(*p)
                elif k == "status":
                    self.current_label.configure(text=p)
                elif k == "finished":
                    self._on_finished()
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _handle_progress(self, p):
        i, t = p["idx"], p["total"]
        self.stat_done.configure(text=str(self.stats["done"]))
        self.stat_fail.configure(text=str(self.stats["failed"]))
        self.progress_bar.set(i/t if t else 0)
        self.percent_label.configure(text=f"{int(i/t*100)}%")
        if p["status"] == "done":
            w, h = p.get("size", (0, 0))
            self.current_label.configure(
                text=f"[{i}/{t}] ✅ {p['name']} → {Path(p['out']).name} "
                     f"({w}×{h})")
            self._log(f"[{i}/{t}] ✅ {p['name']} ({w}×{h})", "success")
        else:
            self.current_label.configure(text=f"[{i}/{t}] ❌ {p['name']}")
            self._log(f"[{i}/{t}] ❌ {p['name']} | {p.get('error','')}",
                      "error")

    def _on_finished(self):
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        elapsed = ""
        if self.start_time:
            s = (datetime.now()-self.start_time).total_seconds()
            elapsed = f"{s:.1f}s" if s < 60 else f"{int(s)//60}m {int(s)%60}s"
        cancelled = self.cancel_flag.is_set()
        self.status_label.configure(
            text="⛔ Cancelled" if cancelled else "✅ Completed")
        self._log("=" * 55, "info")
        self._log(f"🏁 ✅ {self.stats['done']} | ❌ {self.stats['failed']} "
                  f"| ⏱️ {elapsed}", "info")
        self._log("=" * 55, "info")
        if not cancelled and self.stats["done"] > 0:
            if messagebox.askyesno("Completed",
                f"✅ {self.stats['done']} succeeded\n❌ {self.stats['failed']} failed\n"
                f"⏱️ {elapsed}\n\nOpen output folder?"):
                self._open_output()

    def _open_output(self):
        f = self.output_folder
        if not f or not Path(f).exists():
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(f)
            elif sys.platform == "darwin":
                os.system(f'open "{f}"')
            else:
                os.system(f'xdg-open "{f}"')
        except Exception:
            pass

    def _cancel(self):
        if self.is_running:
            self.cancel_flag.set()
            self.status_label.configure(text="⛔ Cancelling...")
            self.cancel_btn.configure(state="disabled")

    def _log(self, text, level="info"):
        prefix = {"info": "•", "success": "✓", "error": "✗",
                  "warn": "⚠"}.get(level, "•")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {prefix} {text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _on_format_change(self, fmt):
        if FORMATS[fmt]["quality"]:
            self.quality_slider.configure(state="normal")
            self.quality_label.configure(text_color=("gray10", "gray90"))
        else:
            self.quality_slider.configure(state="disabled")
            self.quality_label.configure(text_color=("gray55", "gray50"))

    def _on_resize_mode(self, mode):
        self.percent_frame.pack_forget()
        self.custom_frame.pack_forget()
        if mode == "Percent %":
            self.percent_frame.pack(fill="x", padx=14, pady=(0, 14))
        elif mode == "Custom":
            self.custom_frame.pack(fill="x", padx=14, pady=(0, 14))


# ============================================================
def main():
    app = PixelForgeAI()
    app.mainloop()


if __name__ == "__main__":
    main()