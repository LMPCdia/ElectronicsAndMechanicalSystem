# Spec de ejemplo: interfaz RS232 aislada para HF2211A

S = 5.08
OUT = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}   # angulo del pin -> direccion hacia afuera (pantalla)
SPIN = {(-1, 0): "left", (1, 0): "right", (0, 1): "bottom", (0, -1): "up"}
def r(v): return round(v + 0.0, 2)
PARTS = P = []   # (bloque, lib, ref, valor, unit, X, Y, {pin: red})
def part(blk, lib, ref, val, X, Y, nets, unit=1): P.append((blk, lib, ref, val, unit, X, Y, nets))
G = "Device:"
# ---------------- LADO EQUIPO (aislado) ----------------
part("iso", "Connector:DE9_Receptacle", "J1", "DB9 hembra (equipo)", 35.56, 50.8, {"3": "EQ_TX", "5": "GND_ISO"})
part("iso", G+"R", "R1", "100R", 50.8, 50.8, {"1": "EQ_TX", "2": "EQ_A"})
part("iso", G+"D_TVS", "D1", "P6KE15CA", 76.2, 50.8, {"1": "EQ_TX", "2": "GND_ISO"})
part("iso", G+"Polyfuse", "F1", "PTC 50mA/100mA", 101.6, 50.8, {"1": "EQ_A", "2": "EQ_RIN"})
part("iso", "Interface_UART:MAX3232", "U1", "MAX3232CPE", 101.6, 121.92,
     {"1": "U1_C1P", "2": "U1_VP", "3": "U1_C1M", "4": "U1_C2P", "5": "U1_C2M", "6": "U1_VM", "10": "GND_ISO", "11": "GND_ISO",
      "12": "RX_TTL", "13": "EQ_RIN", "15": "GND_ISO", "16": "VISO"})
part("iso", G+"C", "C1", "100nF", 50.8, 91.44, {"1": "U1_C1P", "2": "U1_C1M"})
part("iso", G+"C_Polarized", "C2", "1uF", 66.04, 91.44, {"1": "U1_C2P", "2": "U1_C2M"})
part("iso", G+"C_Polarized", "C3", "1uF", 50.8, 121.92, {"1": "U1_VP", "2": "GND_ISO"})
part("iso", G+"C_Polarized", "C4", "1uF", 66.04, 121.92, {"1": "GND_ISO", "2": "U1_VM"})
part("iso", G+"C", "C5", "100nF", 137.16, 91.44, {"1": "VISO", "2": "GND_ISO"})
for u, (x, y, i, o) in enumerate([(160.02, 76.2, "1", "2"), (160.02, 96.52, "3", "4"), (160.02, 116.84, "5", "6"),
                                  (205.74, 76.2, "9", "8"), (205.74, 96.52, "11", "10"), (205.74, 116.84, "13", "12")], 1):
    nets = {i: "RX_TTL" if u <= 3 else "GND_ISO"}
    if u <= 3: nets[o] = "HC_OUT"
    part("iso", "74xx:74HC04", "U3", "74HC04", x, y, nets, unit=u)
part("iso", "74xx:74HC04", "U3", "74HC04", 160.02, 142.24, {"7": "GND_ISO", "14": "VISO"}, unit=7)
part("iso", G+"C", "C11", "100nF", 185.42, 142.24, {"1": "VISO", "2": "GND_ISO"})
part("iso", G+"R", "R2", "330R", 127.0, 160.02, {"1": "HC_OUT", "2": "LED_A"})
part("iso", G+"R", "R6", "680R", 50.8, 185.42, {"1": "VISO", "2": "LED2_A"})
part("iso", G+"LED", "D3", "LED 5V aislado", 76.2, 190.5, {"1": "GND_ISO", "2": "LED2_A"})
part("iso", G+"R", "R7", "330R carga min.", 101.6, 185.42, {"1": "VISO", "2": "GND_ISO"})
part("iso", G+"C_Polarized", "C15", "10uF", 127.0, 185.42, {"1": "VISO", "2": "GND_ISO"})
# ---------------- BARRERA ----------------
part("bar", "Isolator:6N137", "U4", "6N137", 233.68, 91.44,
     {"2": "LED_A", "3": "GND_ISO", "5": "GND_HF", "6": "OPTO_OUT", "7": "5V_HF", "8": "5V_HF"})
part("bar", "Connector_Generic:Conn_01x04", "DC1", "B0505S-1WR2", 233.68, 160.02,
     {"1": "GND_HF", "2": "5V_HF", "3": "GND_ISO", "4": "VISO"})
part("bar", G+"C", "C12", "100nF", 259.08, 91.44, {"1": "5V_HF", "2": "GND_HF"})
# ---------------- LADO HF2211A ----------------
part("hf", "Interface_UART:MAX3232", "U2", "MAX3232CPE", 330.2, 121.92,
     {"1": "U2_C1P", "2": "U2_VP", "3": "U2_C1M", "4": "U2_C2P", "5": "U2_C2M", "6": "U2_VM", "10": "5V_HF", "11": "OPTO_OUT",
      "14": "HF_RXD", "15": "GND_HF", "16": "5V_HF"})
part("hf", G+"C", "C6", "100nF", 281.94, 91.44, {"1": "U2_C1P", "2": "U2_C1M"})
part("hf", G+"C_Polarized", "C7", "1uF", 297.18, 91.44, {"1": "U2_C2P", "2": "U2_C2M"})
part("hf", G+"C_Polarized", "C8", "1uF", 281.94, 121.92, {"1": "U2_VP", "2": "GND_HF"})
part("hf", G+"C_Polarized", "C9", "1uF", 297.18, 121.92, {"1": "GND_HF", "2": "U2_VM"})
part("hf", G+"C", "C10", "100nF", 365.76, 91.44, {"1": "5V_HF", "2": "GND_HF"})
part("hf", "Connector:DE9_Plug", "J2", "DB9 hacia HF2211A", 391.16, 50.8, {"2": "HF_RXD", "5": "GND_HF"})
part("hf", G+"R", "R3", "1k pull-up", 264.16, 170.18, {"1": "5V_HF", "2": "OPTO_OUT"})
part("hf", G+"R", "R4", "1k LED datos", 289.56, 170.18, {"1": "5V_HF", "2": "LED3_A"})
part("hf", G+"LED", "D4", "LED datos", 289.56, 195.58, {"1": "OPTO_OUT", "2": "LED3_A"})
part("hf", G+"R", "R5", "680R", 314.96, 170.18, {"1": "5V_HF", "2": "LED1_A"})
part("hf", G+"LED", "D2", "LED 5V", 314.96, 195.58, {"1": "GND_HF", "2": "LED1_A"})
part("hf", "Connector:Barrel_Jack_Switch", "JK1", "Jack 5V entrada", 355.6, 170.18, {"1": "5V_HF", "2": "GND_HF", "3": "GND_HF"})
part("hf", "Connector:Barrel_Jack_Switch", "JK2", "Jack 5V al HF2211A", 355.6, 195.58, {"1": "5V_HF", "2": "GND_HF", "3": "GND_HF"})
part("hf", G+"C_Polarized", "C13", "10uF", 386.08, 170.18, {"1": "5V_HF", "2": "GND_HF"})
part("hf", G+"C_Polarized", "C14", "10uF", 386.08, 195.58, {"1": "5V_HF", "2": "GND_HF"})
for k, (ref, nm, x, blk) in enumerate([("TP1", "5V_HF", 264.16, "hf"), ("TP2", "GND_HF", 279.4, "hf"), ("TP3", "VISO", 50.8, "iso"),
                                       ("TP4", "GND_ISO", 66.04, "iso"), ("TP5", "RX_TTL", 81.28, "iso"), ("TP6", "OPTO_OUT", 294.64, "hf")]):
    part(blk, "Connector:TestPoint", ref, nm, x, 228.6, {"1": nm})


RES, RES7 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
CD, CP5 = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
LED = "LED_THT:LED_D3.0mm"; TP = "TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm"
DSUB = "Connector_Dsub:DSUB-9_%s_Horizontal_P2.77x2.84mm_EdgePinOffset7.70mm_Housed_MountingHolesOffset9.12mm"
FOOT = {"J1": DSUB % "Female", "J2": DSUB % "Male",
        "D1": "Diode_THT:D_DO-15_P12.70mm_Horizontal", "F1": "Fuse:Fuse_Bourns_MF-RG300",
        "U1": "Package_DIP:DIP-16_W7.62mm_Socket", "U2": "Package_DIP:DIP-16_W7.62mm_Socket",
        "U3": "Package_DIP:DIP-14_W7.62mm_Socket", "U4": "Package_DIP:DIP-8_W7.62mm_Socket",
        "DC1": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        "JK1": "Connector_BarrelJack:BarrelJack_Horizontal", "JK2": "Connector_BarrelJack:BarrelJack_Horizontal",
        "D2": LED, "D3": LED, "D4": LED, "R4": RES7, "R5": RES7}
for r in ("R1", "R2", "R3", "R6", "R7"): FOOT[r] = RES
for r in ("C1", "C5", "C6", "C10", "C11", "C12"): FOOT[r] = CD
for r in ("C2", "C3", "C4", "C7", "C8", "C9", "C13", "C14", "C15"): FOOT[r] = CP5
for i in range(1, 7): FOOT["TP%d" % i] = TP
HEADERS = [("LADO EQUIPO (5 V aislados)", 20, 30, 2.5), ("BARRERA GALVANICA", 215, 30, 2.5), ("LADO HF2211A (5 V pared)", 270, 30, 2.5)]
NOTES = [("6N137 (opto) y B0505S-1WR2 (DC-DC) son la unica barrera: mantener >= 6 mm entre GND_ISO y GND_HF.\n"
          "Pistas con esquinas a 45 grados (nunca 90).", 215, 215)]
TITLE = "Interfaz RS232 unidireccional aislada para HF2211A"; REV = "A"; COMPANY = "Lautaro Morel Penco"
PROJECT = "PlacaV1.1"; ROOT_UUID = "5b238fdd-67aa-4526-ac19-944940be3fe6"; PAPER = "A3"
