from talon import cron, ctrl, ui, Module, Context, actions, noise, settings, registry
from talon.engine import engine
from talon_plugins import speech, eye_mouse, eye_zoom_mouse
import platform
import subprocess
import ctypes
import os
import pathlib

key = actions.key
self = actions.self
dragging = False
scroll_amount = 0
click_job = None
scroll_job = None
gaze_job = None
cancel_scroll_on_pop = True

default_cursor = {
"AppStarting": "%SystemRoot%\\Cursors\\aero_working.ani",
"Arrow": "%SystemRoot%\\Cursors\\aero_arrow.cur",
"Hand": "%SystemRoot%\\Cursors\\aero_link.cur",
"Help": "%SystemRoot%\\Cursors\\aero_helpsel.cur",
"No": "%SystemRoot%\\Cursors\\aero_unavail.cur",
"NWPen": "%SystemRoot%\\Cursors\\aero_pen.cur",
"Person": "%SystemRoot%\\Cursors\\aero_person.cur",
"Pin": "%SystemRoot%\\Cursors\\aero_pin.cur",
"SizeAll": "%SystemRoot%\\Cursors\\aero_move.cur",
"SizeNESW": "%SystemRoot%\\Cursors\\aero_nesw.cur",
"SizeNS": "%SystemRoot%\\Cursors\\aero_ns.cur",
"SizeNWSE": "%SystemRoot%\\Cursors\\aero_nwse.cur",
"SizeWE": "%SystemRoot%\\Cursors\\aero_ew.cur",
"UpArrow": "%SystemRoot%\Cursors\\aero_up.cur",
"Wait": '%SystemRoot%\\Cursors\\aero_busy.ani',
"Crosshair": "",
"IBeam":"",
}

#todo figure out why notepad++ still shows the cursor sometimes.
hidden_cursor = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Resources\HiddenCursor.cur")

mod = Module()
mod.list('mouse_button',   desc='List of mouse button words to mouse_click index parameter')
mod.setting('mouse_enable_pop_click', 'str')
mod.setting('mouse_enable_pop_stops_scroll', 'str')

ctx = Context()
ctx.settings["user.mouse_enable_pop_click"] = 'False'
ctx.settings["user.mouse_enable_pop_stops_scroll"] = 'False'

ctx.lists['self.mouse_button'] = {
     #right click
     'righty':  '1',
     'rickle': '1',
     
     #left click
     'chiff': '0',
}

@mod.capture
def mouse_index(m) -> int:
    "One mouse button index"
    

@mod.action_class
class Actions:
    def mouse_show_cursor():
        """Shows the cursor"""
        show_cursor_helper(True)
        
    def mouse_hide_cursor():
        """Hides the cursor"""
        show_cursor_helper(False) 
  
    def mouse_wake():
        """Enable control mouse, zoom mouse, and disables cursor"""
        eye_zoom_mouse.zoom_mouse.enable()
        eye_mouse.control_mouse.enable() 
        show_cursor_helper(False)
        
    def mouse_calibrate():
        """Start calibration"""
        eye_mouse.calib_start()
            
    def mouse_toggle_control_mouse():
        """Toggles control mouse"""
        eye_mouse.control_mouse.toggle()

    def mouse_toggle_zoom_mouse():
        """Toggles zoom mouse"""
        if eye_zoom_mouse.zoom_mouse.enabled:
            try:
                eye_zoom_mouse.zoom_mouse.disable()
            except:
                eye_zoom_mouse.zoom_mouse.enabled = False
        else:
            eye_zoom_mouse.zoom_mouse.enable()      
       
    def mouse_cancel_zoom_mouse():
        """Cancel zoom mouse if pending"""
        if eye_zoom_mouse.zoom_mouse.enabled and eye_zoom_mouse.zoom_mouse.state != eye_zoom_mouse.STATE_IDLE:
            eye_zoom_mouse.zoom_mouse.cancel()
    
    def mouse_drag():
        """(TEMPORARY) Press and hold/release button 0 depending on state for dragging"""
        global dragging
        if not dragging:
            dragging = True
            ctrl.mouse_click(button = 0, down = True)
        else:
            dragging = False
            ctrl.mouse_click(up = True)
    
    def mouse_sleep():
        """Disables control mouse, zoom mouse, and re-enables cursor"""
        global dragging        
        eye_zoom_mouse.zoom_mouse.disable()
        eye_mouse.control_mouse.disable() 
        show_cursor_helper(True)
        stop_scroll()
        if dragging:
            mouse_drag()
        
    def mouse_scroll_down():
        """Scrolls down"""
        mouse_scroll(120)()
        
    def mouse_scroll_down_continuous():
        """Scrolls down continuously"""
        mouse_scroll(80)()
        
        if scroll_job is None:
            start_scroll()
        
    def mouse_scroll_up():
        """Scrolls up"""
        mouse_scroll(-120)()
        
    def mouse_scroll_up_continuous():
        """Scrolls up continuously"""
        mouse_scroll(-80)()
        
        if scroll_job is None:
            start_scroll() 

    def mouse_scroll_stop():
        """Stops scrolling"""
        stop_scroll()
        
    def mouse_gaze_scroll():
        """Starts gaze scroll"""
        start_cursor_scrolling()
        
def show_cursor_helper(show):
    """Show/hide the cursor"""
    if "Windows-10" in platform.platform(terse=True):
        import winreg, win32con

        try:
            Registrykey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Control Panel\Cursors", 0, winreg.KEY_WRITE)

            for value_name, value in default_cursor.items():   
                if show: 
                    winreg.SetValueEx(Registrykey, value_name, 0, winreg.REG_EXPAND_SZ, value)
                else:
                    winreg.SetValueEx(Registrykey, value_name, 0, winreg.REG_EXPAND_SZ, hidden_cursor)
                        
            winreg.CloseKey(Registrykey)

            ctypes.windll.user32.SystemParametersInfoA(win32con.SPI_SETCURSORS, 0, None, 0)
            
        except WindowsError:
            print("Unable to show_cursor({})".format(str(show)))
    else:
        ctrl.cursor_visible(show)

def on_pop(active):
    if (gaze_job or scroll_job):
        if registry.settings["user.mouse_enable_pop_stops_scroll"][1] == 'true':
            stop_scroll()
    elif not eye_zoom_mouse.zoom_mouse.enabled and eye_mouse.mouse.attached_tracker is not None:
        if registry.settings["user.mouse_enable_pop_click"][1] == 'true':
            ctrl.mouse_click(button=0, hold=16000)

noise.register('pop', on_pop)
    
def mouse_scroll(amount):
    def scroll():
        global scroll_amount
        if (scroll_amount >= 0) == (amount >= 0):
            scroll_amount += amount
        else:
            scroll_amount = amount
        actions.mouse_scroll(y=int(amount))

    return scroll

def scroll_continuous_helper():
    global scroll_amount
    #print("scroll_continuous_helper")
    if scroll_amount and eye_zoom_mouse.zoom_mouse.state == eye_zoom_mouse.STATE_IDLE:
        actions.mouse_scroll(by_lines=False, y=int(scroll_amount / 10))

def start_scroll():
    global scroll_job
    scroll_job = cron.interval("60ms", scroll_continuous_helper)
    
def gaze_scroll():
    #print("gaze_scroll")
    if eye_zoom_mouse.zoom_mouse.state == eye_zoom_mouse.STATE_IDLE:
        windows = ui.windows()
        window = None
        x, y = ctrl.mouse_pos()
        for w in windows:
            if w.rect.contains(x, y):
                window = w.rect
                break
        if window is None:
            #print("no window found!")
            return
            
        midpoint = window.y + window.height / 2
        amount = int(((y - midpoint) / (window.height / 10)) ** 3)
        actions.mouse_scroll(by_lines=False, y=amount)
    
    #print(f"gaze_scroll: {midpoint} {window.height} {amount}")
    
def stop_scroll():
    global scroll_amount, scroll_job, gaze_job
    scroll_amount = 0
    if scroll_job:
        cron.cancel(scroll_job)
        
    if gaze_job:
        cron.cancel(gaze_job)
        
    scroll_job = None
    gaze_job = None
    
def start_cursor_scrolling():
    global scroll_job, gaze_job
    stop_scroll()
    gaze_job = cron.interval("60ms", gaze_scroll)
    


@ctx.capture(rule='{self.mouse_button}')
def mouse_index(m) -> int:
    return int(m.mouse_button)
    