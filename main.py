from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
from kivy.properties import NumericProperty, ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.utils import platform
import fitz  # PyMuPDF
import json
import os
import glob
import traceback
from collections import OrderedDict

# 平台检测
IS_ANDROID = platform == 'android'

class PDFReaderApp(App):
    title = "PDF阅读器"
    
    def build(self):
        # 设置中文字体（在Android上使用默认字体）
        if not IS_ANDROID:
            from kivy.config import Config
            Config.set('kivy', 'default_font', ['SimHei', 'Arial'])
        return MainLayout()

class MainLayout(FloatLayout):
    current_page = NumericProperty(0)
    total_pages = NumericProperty(0)
    doc = ObjectProperty(None, allownone=True)
    file_path = StringProperty("")
    night_mode = BooleanProperty(False)
    controls_visible = BooleanProperty(True)
    half_page_mode = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super(MainLayout, self).__init__(**kwargs)
        
        # 根据平台设置配置文件路径
        if IS_ANDROID:
            try:
                from android.storage import app_storage_path
                app_data_dir = app_storage_path()
                self.config_file = os.path.join(app_data_dir, "pdf_reader_config.json")
                self.reading_positions_file = os.path.join(app_data_dir, "reading_positions.json")
            except ImportError:
                # 如果android模块不可用，使用当前目录
                self.config_file = "pdf_reader_config.json"
                self.reading_positions_file = "reading_positions.json"
        else:
            # Windows/Linux 开发环境
            self.config_file = "pdf_reader_config.json"
            self.reading_positions_file = "reading_positions.json"
        
        self.page_cache = OrderedDict()
        self.half_page_cache = OrderedDict()
        self.cache_size = 5
        self.touch_start_x = 0
        self.swipe_threshold = 50
        self.load_config()
        self.load_reading_positions()
        
        # 恢复上次打开的文件
        self.restore_last_file()

    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'theme' in config:
                        self.night_mode = (config['theme'] == 'night')
                    if 'half_page_mode' in config:
                        self.half_page_mode = config['half_page_mode']
        except:
            self.night_mode = False
            self.half_page_mode = False

    def save_config(self):
        """保存配置"""
        try:
            config = {
                'theme': 'night' if self.night_mode else 'day',
                'half_page_mode': self.half_page_mode
            }
            
            # 保存当前打开的文件路径
            if hasattr(self, 'file_path') and self.file_path:
                config['last_file'] = self.file_path
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_reading_positions(self):
        """加载阅读位置记录"""
        self.reading_positions = {}
        try:
            if os.path.exists(self.reading_positions_file):
                with open(self.reading_positions_file, 'r', encoding='utf-8') as f:
                    self.reading_positions = json.load(f)
                    print(f"已加载阅读位置记录: {len(self.reading_positions)} 个文件")
        except Exception as e:
            print(f"加载阅读位置失败: {e}")
            self.reading_positions = {}

    def save_reading_positions(self):
        """保存阅读位置记录"""
        try:
            with open(self.reading_positions_file, 'w', encoding='utf-8') as f:
                json.dump(self.reading_positions, f, ensure_ascii=False, indent=2)
            print(f"已保存阅读位置记录: {len(self.reading_positions)} 个文件")
        except Exception as e:
            print(f"保存阅读位置失败: {e}")

    def get_reading_position(self, file_path):
        """获取文件的阅读位置"""
        file_key = os.path.abspath(file_path)
        if file_key in self.reading_positions:
            position = self.reading_positions[file_key]
            print(f"找到阅读位置: {file_path} -> 第 {position + 1} 页")
            return position
        return 0

    def save_reading_position(self, file_path, page_number):
        """保存文件的阅读位置"""
        try:
            file_key = os.path.abspath(file_path)
            self.reading_positions[file_key] = page_number
            self.save_reading_positions()
            print(f"保存阅读位置: {file_path} -> 第 {page_number + 1} 页")
        except Exception as e:
            print(f"保存阅读位置失败: {e}")

    def restore_last_file(self):
        """恢复上次打开的文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'last_file' in config and config['last_file']:
                        last_file = config['last_file']
                        if os.path.exists(last_file):
                            Clock.schedule_once(lambda dt: self.load_pdf_file(last_file), 0.5)
                            return
            
            # 如果没有上次打开的文件，显示文件列表
            self.show_file_list()
        except Exception as e:
            print(f"恢复上次文件失败: {e}")
            self.show_file_list()

    def toggle_night_mode(self):
        """切换夜间模式"""
        self.night_mode = not self.night_mode
        self.save_config()
        if hasattr(self, 'doc') and self.doc:
            self.create_reader_interface()
        else:
            self.show_file_list()

    def toggle_half_page_mode(self):
        """切换半边页阅读模式"""
        self.half_page_mode = not self.half_page_mode
        self.save_config()
        if hasattr(self, 'doc') and self.doc:
            if self.half_page_mode and not hasattr(self, 'current_half_page'):
                self.current_half_page = 'right'
            self.display_current_page()

    def toggle_controls(self):
        """切换控制按钮显示/隐藏"""
        self.controls_visible = not self.controls_visible
        print(f"控制栏显示: {self.controls_visible}")
        
        if hasattr(self, 'top_bar'):
            self.top_bar.opacity = 1 if self.controls_visible else 0
        
        if hasattr(self, 'bottom_bar'):
            self.bottom_bar.opacity = 1 if self.controls_visible else 0

    def get_bg_color(self):
        """获取背景颜色"""
        return (0.1, 0.1, 0.1, 1) if self.night_mode else (1, 1, 1, 1)

    def get_text_color(self):
        """获取文字颜色"""
        return (1, 1, 1, 1) if self.night_mode else (0, 0, 0, 1)

    def get_button_color(self):
        """获取按钮颜色"""
        if self.night_mode:
            return (0.3, 0.5, 0.7, 1)
        else:
            return (0.2, 0.6, 0.8, 1)

    def show_file_list(self, instance=None):
        """显示文件列表界面"""
        self.clear_widgets()
        self.page_cache.clear()
        self.half_page_cache.clear()
        
        if hasattr(self, 'doc') and self.doc and self.file_path:
            self.save_reading_position(self.file_path, self.current_page)
            self.doc.close()
            self.doc = None
        
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        with main_layout.canvas.before:
            Color(*self.get_bg_color())
            self.bg_rect = Rectangle(pos=main_layout.pos, size=main_layout.size)
        
        main_layout.bind(pos=self.update_bg_rect, size=self.update_bg_rect)
        
        # 顶部控制栏
        top_bar = BoxLayout(
            orientation='horizontal',
            size_hint_y=0.1,
            padding=5,
            spacing=5
        )
        
        title_label = Label(
            text='PDF阅读器', 
            font_size='18sp', 
            bold=True,
            size_hint_x=0.6,
            color=self.get_text_color()
        )
        
        night_mode_btn = Button(
            text='夜间模式' if not self.night_mode else '日间模式',
            size_hint_x=0.4,
            font_size='16sp',
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        night_mode_btn.bind(on_release=lambda x: self.toggle_night_mode())
        
        top_bar.add_widget(title_label)
        top_bar.add_widget(night_mode_btn)
        main_layout.add_widget(top_bar)
        
        # 文件列表区域
        content_layout = BoxLayout(orientation='vertical', size_hint_y=0.9)
        self.update_file_list(content_layout)
        main_layout.add_widget(content_layout)
        
        self.add_widget(main_layout)

    def update_bg_rect(self, instance, value):
        """更新背景矩形大小"""
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size

    def update_file_list(self, content_layout):
        """更新文件列表"""
        pdf_files = self.scan_pdf_files()
        
        if pdf_files:
            scroll_view = ScrollView()
            file_list = BoxLayout(orientation='vertical', size_hint_y=None)
            file_list.bind(minimum_height=file_list.setter('height'))
            
            for pdf_file in pdf_files:
                file_name = os.path.basename(pdf_file)
                if len(file_name) > 30:
                    file_name = file_name[:27] + "..."
                
                last_position = self.get_reading_position(pdf_file)
                if last_position > 0:
                    file_name += f" (读到第{last_position + 1}页)"
                    
                file_btn = Button(
                    text=file_name,
                    size_hint_y=None,
                    height=60,
                    font_size='14sp',
                    background_color=self.get_button_color(),
                    color=(1, 1, 1, 1),
                    background_normal=''
                )
                file_btn.bind(on_release=lambda btn, path=pdf_file: self.load_pdf_file(path))
                file_list.add_widget(file_btn)
            
            scroll_view.add_widget(file_list)
            content_layout.add_widget(scroll_view)
        else:
            no_files_label = Label(
                text='未找到PDF文件\n请将PDF文件放在程序目录',
                font_size='16sp',
                halign='center',
                color=self.get_text_color()
            )
            content_layout.add_widget(no_files_label)

    def scan_pdf_files(self):
        """扫描PDF文件"""
        pdf_files = []
        
        if not IS_ANDROID:
            # 只在PC环境扫描文件
            current_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                pdf_files = glob.glob(os.path.join(current_dir, "*.pdf"))
                print(f"找到 {len(pdf_files)} 个PDF文件")
            except Exception as e:
                print(f"扫描错误: {e}")
        
        return pdf_files[:10]

    def load_pdf_file(self, file_path):
        """加载PDF文件"""
        print(f"加载文件: {file_path}")
        try:
            if not os.path.exists(file_path):
                self.show_message("文件不存在")
                return
            
            self.file_path = file_path
            self.doc = fitz.open(file_path)
            self.total_pages = len(self.doc)
            
            self.current_page = self.get_reading_position(file_path)
            
            if self.current_page >= self.total_pages:
                self.current_page = self.total_pages - 1
            
            print(f"跳转到上次阅读位置: 第 {self.current_page + 1} 页")
            
            if self.half_page_mode:
                self.current_half_page = 'right'
            
            self.preload_pages()
            self.create_reader_interface()
            
        except Exception as e:
            print(f"加载失败: {e}")
            self.show_message(f"加载失败: {str(e)}")
    
    def preload_pages(self):
        """预加载页面到缓存"""
        if not self.doc:
            return
            
        # 预加载当前页和前后几页
        start_page = max(0, self.current_page - 2)
        end_page = min(self.total_pages - 1, self.current_page + 2)
        
        for page_num in range(start_page, end_page + 1):
            if page_num not in self.page_cache:
                self._load_page_to_cache(page_num)
    
    def _load_page_to_cache(self, page_num):
        """加载指定页面到缓存"""
        try:
            page = self.doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # 添加到缓存
            self.page_cache[page_num] = img_data
            
            # 保持缓存大小
            if len(self.page_cache) > self.cache_size:
                # 移除最旧的页面
                oldest_page = next(iter(self.page_cache))
                del self.page_cache[oldest_page]
                
        except Exception as e:
            print(f"预加载页面 {page_num} 失败: {e}")
    
    def _load_half_page_to_cache(self, page_num, is_left_half):
        """加载半边页面到缓存"""
        try:
            page = self.doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            
            # 获取页面尺寸
            rect = page.rect
            width = rect.width
            height = rect.height
            
            # 计算半边页的矩形区域
            if is_left_half:
                clip_rect = fitz.Rect(0, 0, width/2, height)
            else:
                clip_rect = fitz.Rect(width/2, 0, width, height)
            
            pix = page.get_pixmap(matrix=mat, clip=clip_rect)
            img_data = pix.tobytes("png")
            
            # 添加到半边页缓存
            cache_key = (page_num, is_left_half)
            self.half_page_cache[cache_key] = img_data
            
            # 保持缓存大小
            if len(self.half_page_cache) > self.cache_size * 2:
                oldest_page = next(iter(self.half_page_cache))
                del self.half_page_cache[oldest_page]
                
        except Exception as e:
            print(f"预加载半边页面 {page_num} 失败: {e}")
    
    def create_reader_interface(self):
        self.clear_widgets()
        
        # 主布局
        main_layout = FloatLayout()
        
        # 设置背景色
        with main_layout.canvas.before:
            Color(*self.get_bg_color())
            self.reader_bg_rect = Rectangle(pos=main_layout.pos, size=main_layout.size)
        
        main_layout.bind(pos=self.update_reader_bg_rect, size=self.update_reader_bg_rect)
        
        # 顶部控制栏
        self.top_bar = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.1),
            pos_hint={'top': 1},
            padding=10,
            spacing=10
        )
        
        back_btn = Button(
            text='浏览文件', 
            size_hint_x=0.2,
            font_size='14sp',
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        back_btn.bind(on_release=self.show_file_list)
        
        title_label = Label(
            text=os.path.basename(self.file_path),
            size_hint_x=0.4,
            font_size='16sp',
            color=self.get_text_color()
        )
        
        half_page_btn = Button(
            text='整页' if self.half_page_mode else '半页',
            size_hint_x=0.2,
            font_size='14sp',
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        half_page_btn.bind(on_release=lambda x: self.toggle_half_page_mode())
        
        night_mode_btn = Button(
            text='夜间模式' if not self.night_mode else '日间模式',
            size_hint_x=0.2,
            font_size='14sp',
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        night_mode_btn.bind(on_release=lambda x: self.toggle_night_mode())
        
        self.top_bar.add_widget(back_btn)
        self.top_bar.add_widget(title_label)
        self.top_bar.add_widget(half_page_btn)
        self.top_bar.add_widget(night_mode_btn)
        
        # 底部控制栏
        self.bottom_bar = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.1),
            pos_hint={'x': 0, 'y': 0},
            padding=10,
            spacing=10
        )
        
        next_btn = Button(
            text='下一页', 
            size_hint_x=0.3,
            font_size='14sp',
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        next_btn.bind(on_release=self.next_page)
        
        self.page_label = Label(
            text=f'{self.current_page + 1}/{self.total_pages}',
            size_hint_x=0.4,
            font_size='16sp',
            color=self.get_text_color(),
            bold=True
        )
        
        prev_btn = Button(
            text='上一页', 
            size_hint_x=0.3,
            font_size='14sp',
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        prev_btn.bind(on_release=self.previous_page)
        
        self.bottom_bar.add_widget(next_btn)
        self.bottom_bar.add_widget(self.page_label)
        self.bottom_bar.add_widget(prev_btn)
        
        # PDF显示区域
        self.scroll_view = ScrollView(
            size_hint=(1, 0.8),
            pos_hint={'x': 0, 'y': 0.1},
            do_scroll_x=True,
            do_scroll_y=True,
            scroll_type=['bars', 'content']
        )
        
        self.scroll_view.bind(on_touch_down=self.on_scroll_view_touch_down)
        self.scroll_view.bind(on_touch_up=self.on_scroll_view_touch_up)
        
        self.pdf_display = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            padding=10
        )
        self.pdf_display.bind(minimum_size=self.pdf_display.setter('size'))
        
        self.scroll_view.add_widget(self.pdf_display)
        
        self.display_current_page()
        
        main_layout.add_widget(self.top_bar)
        main_layout.add_widget(self.bottom_bar)
        main_layout.add_widget(self.scroll_view)
        
        self.add_widget(main_layout)
    
    def on_scroll_view_touch_down(self, instance, touch):
        """处理PDF显示区域的触摸按下事件"""
        if instance.collide_point(*touch.pos):
            top_bar_clicked = (hasattr(self, 'top_bar') and 
                              self.top_bar.collide_point(*touch.pos) and 
                              self.top_bar.opacity > 0)
            
            bottom_bar_clicked = (hasattr(self, 'bottom_bar') and 
                                 self.bottom_bar.collide_point(*touch.pos) and 
                                 self.bottom_bar.opacity > 0)
            
            if not top_bar_clicked and not bottom_bar_clicked:
                self.touch_start_x = touch.x
                self.touch_start_y = touch.y
                self.touch_start_time = touch.time_start
                return True
        return False

    def on_scroll_view_touch_up(self, instance, touch):
        """处理PDF显示区域的触摸释放事件"""
        if instance.collide_point(*touch.pos) and hasattr(self, 'touch_start_x'):
            delta_x = touch.x - self.touch_start_x
            delta_y = touch.y - self.touch_start_y
            click_duration = touch.time_end - getattr(self, 'touch_start_time', touch.time_end)
            
            if abs(delta_x) < 20 and abs(delta_y) < 20 and click_duration < 0.5:
                self.toggle_controls()
                return True
            
            if abs(delta_x) > self.swipe_threshold and abs(delta_y) < self.swipe_threshold * 2:
                if delta_x > 0:
                    self.previous_page(None)
                else:
                    self.next_page(None)
                return True
            
            self.touch_start_x = 0
            self.touch_start_y = 0
            return True
        return False
    
    def update_reader_bg_rect(self, instance, value):
        """更新阅读界面背景矩形大小"""
        if hasattr(self, 'reader_bg_rect'):
            self.reader_bg_rect.pos = instance.pos
            self.reader_bg_rect.size = instance.size
    
    def display_current_page(self):
        self.pdf_display.clear_widgets()
        
        if not self.doc:
            return
        
        try:
            Clock.schedule_once(lambda dt: self._render_page(), 0)
            
        except Exception as e:
            print(f"显示页面错误: {e}")
            error_label = Label(
                text=f"错误: {str(e)}", 
                font_size='14sp',
                color=(1, 0, 0, 1)
            )
            self.pdf_display.add_widget(error_label)
    
    def _render_page(self):
        try:
            self.pdf_display.clear_widgets()
            
            if self.half_page_mode:
                if not hasattr(self, 'current_half_page'):
                    self.current_half_page = 'right'
                
                is_left_half = (self.current_half_page == 'left')
                cache_key = (self.current_page, is_left_half)
                
                if cache_key in self.half_page_cache:
                    img_data = self.half_page_cache[cache_key]
                    print(f"从缓存加载半边页面 {self.current_page + 1} ({self.current_half_page})")
                else:
                    self._load_half_page_to_cache(self.current_page, is_left_half)
                    img_data = self.half_page_cache.get(cache_key)
                    print(f"渲染半边页面 {self.current_page + 1} ({self.current_half_page})")
                
                half_page_indicator = "左" if is_left_half else "右"
                self.page_label.text = f'{self.current_page + 1}/{self.total_pages} ({half_page_indicator})'
                
            else:
                if self.current_page in self.page_cache:
                    img_data = self.page_cache[self.current_page]
                    print(f"从缓存加载页面 {self.current_page + 1}")
                else:
                    page = self.doc[self.current_page]
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    self.page_cache[self.current_page] = img_data
                    print(f"渲染页面 {self.current_page + 1}, 尺寸: {pix.width}x{pix.height}")
                
                self.page_label.text = f'{self.current_page + 1}/{self.total_pages}'
            
            if not img_data:
                raise Exception("无法获取页面图像数据")
            
            from kivy.core.image import Image as CoreImage
            from io import BytesIO
            
            data = BytesIO(img_data)
            core_image = CoreImage(data, ext='png')
            
            pdf_image = Image(
                texture=core_image.texture,
                keep_ratio=True,
                allow_stretch=False,
                size_hint=(None, None)
            )
            
            display_width = Window.width - 40
            ratio = display_width / core_image.texture.width
            display_height = core_image.texture.height * ratio
            
            max_display_height = Window.height * 0.8 - 40
            if display_height > max_display_height:
                ratio = max_display_height / core_image.texture.height
                display_width = core_image.texture.width * ratio
                display_height = max_display_height
            
            pdf_image.size = (display_width, display_height)
            
            horizontal_center_layout = BoxLayout(
                orientation='horizontal',
                size_hint=(None, None),
                size=(Window.width, max(display_height, Window.height * 0.8 - 40)),
                padding=0
            )
            
            if display_width < Window.width:
                left_spacer = BoxLayout(size_hint_x=None, width=(Window.width - display_width) / 2)
                horizontal_center_layout.add_widget(left_spacer)
            
            vertical_center_layout = BoxLayout(
                orientation='vertical',
                size_hint=(None, None),
                size=(display_width, max(display_height, Window.height * 0.8 - 40)),
                padding=0
            )
            
            if display_height < Window.height * 0.8 - 40:
                top_spacer = BoxLayout(size_hint_y=None, height=(Window.height * 0.8 - 40 - display_height) / 2)
                vertical_center_layout.add_widget(top_spacer)
            
            vertical_center_layout.add_widget(pdf_image)
            
            if display_height < Window.height * 0.8 - 40:
                bottom_spacer = BoxLayout(size_hint_y=None, height=(Window.height * 0.8 - 40 - display_height) / 2)
                vertical_center_layout.add_widget(bottom_spacer)
            
            horizontal_center_layout.add_widget(vertical_center_layout)
            
            if display_width < Window.width:
                right_spacer = BoxLayout(size_hint_x=None, width=(Window.width - display_width) / 2)
                horizontal_center_layout.add_widget(right_spacer)
            
            self.pdf_display.add_widget(horizontal_center_layout)
            
            self.scroll_view.scroll_y = 1
            
            print("页面渲染完成")
            
            Clock.schedule_once(lambda dt: self._preload_adjacent_pages(), 0.1)
            
        except Exception as e:
            print(f"渲染错误: {e}")
            traceback.print_exc()
            error_label = Label(
                text=f"渲染失败: {str(e)}", 
                font_size='14sp',
                color=(1, 0, 0, 1)
            )
            self.pdf_display.add_widget(error_label)
    
    def _preload_adjacent_pages(self):
        """预加载相邻页面"""
        if self.half_page_mode:
            current_cache_key = (self.current_page, self.current_half_page == 'left')
            opposite_cache_key = (self.current_page, self.current_half_page != 'left')
            
            if opposite_cache_key not in self.half_page_cache:
                self._load_half_page_to_cache(self.current_page, self.current_half_page != 'left')
        else:
            if self.current_page < self.total_pages - 1 and (self.current_page + 1) not in self.page_cache:
                self._load_page_to_cache(self.current_page + 1)
            
            if self.current_page > 0 and (self.current_page - 1) not in self.page_cache:
                self._load_page_to_cache(self.current_page - 1)
    
    def next_page(self, instance):
        if self.half_page_mode and hasattr(self, 'current_half_page'):
            if self.current_half_page == 'right':
                self.current_half_page = 'left'
                self.display_current_page()
            else:
                if self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    self.current_half_page = 'right'
                    self.display_current_page()
                    if self.file_path:
                        self.save_reading_position(self.file_path, self.current_page)
        else:
            if self.current_page < self.total_pages - 1:
                self.current_page += 1
                self.display_current_page()
                if self.file_path:
                    self.save_reading_position(self.file_path, self.current_page)
    
    def previous_page(self, instance):
        if self.half_page_mode and hasattr(self, 'current_half_page'):
            if self.current_half_page == 'left':
                self.current_half_page = 'right'
                self.display_current_page()
            else:
                if self.current_page > 0:
                    self.current_page -= 1
                    self.current_half_page = 'left'
                    self.display_current_page()
                    if self.file_path:
                        self.save_reading_position(self.file_path, self.current_page)
        else:
            if self.current_page > 0:
                self.current_page -= 1
                self.display_current_page()
                if self.file_path:
                    self.save_reading_position(self.file_path, self.current_page)
    
    def show_message(self, message):
        """显示消息弹窗"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=20)
        content.add_widget(Label(text=message, color=self.get_text_color()))
        
        ok_btn = Button(
            text='确定', 
            size_hint_y=0.3,
            background_color=self.get_button_color(),
            color=(1, 1, 1, 1),
            background_normal=''
        )
        popup = Popup(
            title='提示', 
            content=content, 
            size_hint=(0.6, 0.4),
            background_color=self.get_bg_color(),
            title_color=self.get_text_color(),
            separator_color=self.get_button_color()
        )
        ok_btn.bind(on_release=popup.dismiss)
        content.add_widget(ok_btn)
        popup.open()

if __name__ == '__main__':
    Window.size = (400, 600)
    Window.clearcolor = (1, 1, 1, 1)
    
    try:
        import fitz
    except ImportError:
        print("请安装PyMuPDF: pip install PyMuPDF")
        exit(1)
        
    PDFReaderApp().run()
