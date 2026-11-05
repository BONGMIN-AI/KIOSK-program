"""SV1520 계열 USB HID 배지 리더 원시 입력 시험 (Windows, 추가 패키지 불필요).

실행: python -u test_sv1520_hid.py
장치 VID/PID가 다르면 --vid 0x.... --pid 0x.... 로 지정한다.
태그 데이터는 화면에만 출력하며 파일로 저장하지 않는다.
"""

import argparse
import ctypes as C
from ctypes import wintypes as W


class GUID(C.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD),
                ("Data4", C.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", W.DWORD), ("Reserved", C.c_void_p)]


class HIDD_ATTRIBUTES(C.Structure):
    _fields_ = [("Size", W.ULONG), ("VendorID", W.USHORT),
                ("ProductID", W.USHORT), ("VersionNumber", W.USHORT)]


class HIDP_CAPS(C.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT),
                ("InputReportByteLength", W.USHORT),
                ("OutputReportByteLength", W.USHORT),
                ("FeatureReportByteLength", W.USHORT),
                ("Reserved", W.USHORT * 17),
                ("NumberLinkCollectionNodes", W.USHORT),
                ("NumberInputButtonCaps", W.USHORT),
                ("NumberInputValueCaps", W.USHORT),
                ("NumberInputDataIndices", W.USHORT),
                ("NumberOutputButtonCaps", W.USHORT),
                ("NumberOutputValueCaps", W.USHORT),
                ("NumberOutputDataIndices", W.USHORT),
                ("NumberFeatureButtonCaps", W.USHORT),
                ("NumberFeatureValueCaps", W.USHORT),
                ("NumberFeatureDataIndices", W.USHORT)]


hid = C.WinDLL("hid")
setup = C.WinDLL("setupapi")
kernel = C.WinDLL("kernel32", use_last_error=True)
hid.HidD_GetHidGuid.argtypes = [C.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [W.HANDLE, C.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.argtypes = [W.HANDLE, C.POINTER(C.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [C.c_void_p]
hid.HidP_GetCaps.argtypes = [C.c_void_p, C.POINTER(HIDP_CAPS)]
setup.SetupDiGetClassDevsW.argtypes = [C.POINTER(GUID), C.c_void_p, W.HWND, W.DWORD]
setup.SetupDiGetClassDevsW.restype = W.HANDLE
setup.SetupDiEnumDeviceInterfaces.argtypes = [W.HANDLE, C.c_void_p, C.POINTER(GUID), W.DWORD, C.POINTER(SP_DEVICE_INTERFACE_DATA)]
setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [W.HANDLE, C.POINTER(SP_DEVICE_INTERFACE_DATA), C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
setup.SetupDiDestroyDeviceInfoList.argtypes = [W.HANDLE]
kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
kernel.CreateFileW.restype = W.HANDLE
kernel.ReadFile.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
kernel.CloseHandle.argtypes = [W.HANDLE]
INVALID = C.c_void_p(-1).value


def card_uid(raw):
    """관찰된 SV1520 보고서: 00 0A 00 63 90 00 04 [UID 4바이트] 08 ..."""
    if len(raw) >= 12 and raw[:7] == bytes.fromhex("00 0A 00 63 90 00 04"):
        return raw[7:11].hex().upper()
    return None


def hid_paths():
    guid = GUID()
    hid.HidD_GetHidGuid(C.byref(guid))
    info = setup.SetupDiGetClassDevsW(C.byref(guid), None, None, 0x12)
    if info == INVALID:
        raise C.WinError(C.get_last_error())
    try:
        index = 0
        while True:
            item = SP_DEVICE_INTERFACE_DATA()
            item.cbSize = C.sizeof(item)
            if not setup.SetupDiEnumDeviceInterfaces(info, None, C.byref(guid), index, C.byref(item)):
                break
            needed = W.DWORD()
            setup.SetupDiGetDeviceInterfaceDetailW(info, C.byref(item), None, 0, C.byref(needed), None)
            buf = C.create_string_buffer(needed.value)
            C.cast(buf, C.POINTER(W.DWORD)).contents.value = 8 if C.sizeof(C.c_void_p) == 8 else 6
            if setup.SetupDiGetDeviceInterfaceDetailW(info, C.byref(item), buf, needed, C.byref(needed), None):
                yield C.wstring_at(C.addressof(buf) + 4)
            index += 1
    finally:
        setup.SetupDiDestroyDeviceInfoList(info)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vid", type=lambda x: int(x, 0), default=0x0483)
    parser.add_argument("--pid", type=lambda x: int(x, 0), default=0x572B)
    args = parser.parse_args()
    found = 0
    for path in hid_paths():
        handle = kernel.CreateFileW(path, 0x80000000, 3, None, 3, 0, None)
        if handle == INVALID:
            continue
        attr = HIDD_ATTRIBUTES()
        attr.Size = C.sizeof(attr)
        if not hid.HidD_GetAttributes(handle, C.byref(attr)) or (attr.VendorID, attr.ProductID) != (args.vid, args.pid):
            kernel.CloseHandle(handle)
            continue
        found += 1
        pre = C.c_void_p()
        caps = HIDP_CAPS()
        if not hid.HidD_GetPreparsedData(handle, C.byref(pre)):
            print("HID 정보 읽기 실패")
            kernel.CloseHandle(handle)
            continue
        try:
            status = hid.HidP_GetCaps(pre, C.byref(caps))
        finally:
            hid.HidD_FreePreparsedData(pre)
        length = caps.InputReportByteLength
        print(f"HID 장치 발견: VID_{attr.VendorID:04X}&PID_{attr.ProductID:04X}, UsagePage=0x{caps.UsagePage:04X}, Usage=0x{caps.Usage:04X}, 입력 보고서={length}바이트, 상태=0x{status & 0xFFFFFFFF:08X}", flush=True)
        if not length:
            print("이 HID 인터페이스에는 읽을 입력 보고서가 없습니다.")
            kernel.CloseHandle(handle)
            continue
        print("태그를 대세요. 수신 바이트를 16진수와 문자로 표시합니다. 종료: Ctrl+C", flush=True)
        try:
            while True:
                data = C.create_string_buffer(length)
                count = W.DWORD()
                if not kernel.ReadFile(handle, data, length, C.byref(count), None):
                    raise C.WinError(C.get_last_error())
                raw = data.raw[:count.value]
                print(f"수신 {len(raw)}바이트: {raw.hex(' ')} | 문자: {''.join(chr(b) if 32 <= b < 127 else '.' for b in raw)}", flush=True)
                uid = card_uid(raw)
                if uid:
                    print(f"카드 UID: {uid}", flush=True)
                else:
                    print("UID 형식 미확인: 원시 데이터를 확인하세요.", flush=True)
        except KeyboardInterrupt:
            print("\n시험 종료")
        finally:
            kernel.CloseHandle(handle)
        return 0
    if not found:
        print(f"대상 HID 장치 VID_{args.vid:04X}&PID_{args.pid:04X}를 열지 못했습니다.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
