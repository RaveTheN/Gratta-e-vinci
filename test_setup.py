"""
Test setup script to verify all dependencies and basic functionality
"""
import sys
import importlib

def test_imports():
    """Test if all required modules can be imported"""
    required_modules = [
        'asyncio',
        'pyautogui', 
        'pytesseract',
        'cv2',
        'numpy',
        'PIL',
        'time',
        'random',
        'math'
    ]
    
    print("=== Testing Module Imports ===")
    failed_imports = []
    
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - FAILED: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n⚠️  Missing modules: {failed_imports}")
        print("Run: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ All modules imported successfully!")
        return True

def test_pyautogui():
    """Test pyautogui basic functionality"""
    print("\n=== Testing PyAutoGUI ===")
    try:
        import pyautogui
        
        # Get screen size
        width, height = pyautogui.size()
        print(f"Screen size: {width}x{height}")
        
        # Get current mouse position
        x, y = pyautogui.position()
        print(f"Current mouse position: ({x}, {y})")
        
        # Test screenshot capability
        screenshot = pyautogui.screenshot()
        print(f"Screenshot taken: {screenshot.size}")
        
        print("✅ PyAutoGUI working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ PyAutoGUI error: {e}")
        return False

def test_tesseract():
    """Test if Tesseract OCR is properly installed"""
    print("\n=== Testing Tesseract OCR ===")
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Create a simple test image with text
        img_array = np.ones((100, 200, 3), dtype=np.uint8) * 255  # White background
        test_img = Image.fromarray(img_array)
        
        # Try to extract text (should be empty but shouldn't crash)
        text = pytesseract.image_to_string(test_img)
        print("✅ Tesseract OCR working!")
        return True
        
    except pytesseract.TesseractNotFoundError:
        print("❌ Tesseract not found! Please install Tesseract OCR:")
        print("   Download from: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   Or set path: pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")
        return False
    except Exception as e:
        print(f"❌ Tesseract error: {e}")
        return False

def test_basic_functionality():
    """Test basic script functionality without mouse automation"""
    print("\n=== Testing Basic Script Functions ===")
    try:
        # Import our script classes/functions
        sys.path.append('.')
        
        # Test Point class
        from playM import Point
        p = Point(100, 200)
        print(f"✅ Point class: {p}")
        
        # Test some utility functions
        from playM import get_random_number, log_state
        rand_num = get_random_number()
        print(f"✅ Random number: {rand_num}")
        
        print("✅ Basic script functions working!")
        return True
        
    except Exception as e:
        print(f"❌ Script error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Starting test suite for playM.py\n")
    
    tests = [
        test_imports,
        test_pyautogui, 
        test_tesseract,
        test_basic_functionality
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print("-" * 50)
    
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed! You can run the main script.")
        print("⚠️  WARNING: The main script will control your mouse and keyboard!")
        print("   Make sure to position your game window correctly before running.")
    else:
        print("❌ Some tests failed. Please fix the issues before running the main script.")

if __name__ == "__main__":
    main()
