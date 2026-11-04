"""Campfire Aftercare wiring schematic, drawn with Schemdraw 0.23.

Nets with the same label (3V3, GND, SDA, SCL, GPIO26, GPIO25) are connected.
Run:  python schematic.py   -> img/schematic.svg, img/schematic.png
"""
from pathlib import Path
import schemdraw
import schemdraw.elements as elm

OUTPUT = Path(__file__).resolve().parent / 'img'
OUTPUT.mkdir(exist_ok=True)

schemdraw.config(fontsize=11, lw=1.2, font='sans-serif')


def net(d, at, direction, name, length=0.8, ground=False):
    """Short wire ending in a net label (or a ground symbol)."""
    line = elm.Line().at(at)
    line = getattr(line, direction)(length)
    d += line
    if ground:
        d += elm.Ground()
    else:
        loc = {'left': 'left', 'right': 'right', 'up': 'top', 'down': 'bottom'}[direction]
        d += elm.Dot(open=True).label(name, loc=loc, fontsize=10, color='#1f4e9c')


with schemdraw.Drawing(file=None, show=False) as d:
    d.config(unit=2.0)

    # ---------------- FireBeetle ----------------
    # Schemdraw orders pins on a side from bottom to top, so lists are reversed.
    mcu = elm.Ic(
        pins=[elm.IcPin(name='GPIO26', side='left', anchorname='P26'),
              elm.IcPin(name='GPIO22 / SCL', side='left', anchorname='SCL'),
              elm.IcPin(name='GPIO21 / SDA', side='left', anchorname='SDA'),
              elm.IcPin(name='GND', side='left', anchorname='GNDL'),
              elm.IcPin(name='3V3', side='left', anchorname='V33'),
              elm.IcPin(name='GND', side='right', anchorname='GNDR'),
              elm.IcPin(name='GPIO4', side='right', anchorname='P4'),
              elm.IcPin(name='GPIO27', side='right', anchorname='P27'),
              elm.IcPin(name='GPIO13', side='right', anchorname='P13'),
              elm.IcPin(name='GPIO14', side='right', anchorname='P14'),
              elm.IcPin(name='GPIO25 (DAC1)', side='bottom', anchorname='P25')],
        pinspacing=1.1, edgepadW=4.2, edgepadH=1.4, leadlen=0.5,
    ).at((0, 0))
    d += mcu
    bb = mcu.get_bbox(transform=True)
    d += elm.Label().at((mcu.center[0], bb.ymax + 0.7)).label('FireBeetle 2 ESP32-E (DFR0654-F) · USB 5 V', fontsize=12)

    net(d, mcu.V33, 'left', '3V3')
    net(d, mcu.GNDL, 'left', '', ground=False)
    d += elm.Ground().at(d.here)
    net(d, mcu.SDA, 'left', 'SDA')
    net(d, mcu.SCL, 'left', 'SCL')
    net(d, mcu.P26, 'left', 'PUMP_SIG')
    d += elm.Line().at(mcu.P25).down(0.6)
    d += elm.Dot(open=True).label('AUDIO', loc='bottom', fontsize=10, color='#1f4e9c')

    # ---------------- Four LEDs ----------------
    rows = [('P14', 'green', 'Green: person in view'),
            ('P13', 'gold', 'Yellow: tank low'),
            ('P27', 'red', 'Red: bowl ≥ 45 °C'),
            ('P4', 'blue', 'Blue: heart recognised')]
    ends = []
    for anchor, colour, text in rows:
        d += elm.Line().at(getattr(mcu, anchor)).right(0.5)
        d += elm.Resistor().right(2.0).label('330 Ω', fontsize=9)
        d += elm.LED().right(1.6).color(colour)
        ends.append(d.here)
    rail = ends[0][0] + 0.8
    for (anchor, colour, text), p in zip(rows, ends):
        d += elm.Line().at(p).tox(rail)
    d += elm.Line().at((rail, ends[0][1])).toy(mcu.GNDR[1])
    d += elm.Line().at(mcu.GNDR).tox(rail)
    d += elm.Dot().at((rail, mcu.GNDR[1]))
    d += elm.Ground().at((rail, mcu.GNDR[1]))
    for (anchor, colour, text), p in zip(rows, ends):
        d += elm.Label().at((rail + 0.4, p[1])).label(text, loc='right', halign='left', fontsize=10)

    # ---------------- I2C sensors (left) ----------------
    def sensor(title):
        return elm.Ic(pins=[elm.IcPin(name='SCL', side='right', anchorname='SCL'),
                            elm.IcPin(name='SDA', side='right', anchorname='SDA'),
                            elm.IcPin(name='GND', side='right', anchorname='GND'),
                            elm.IcPin(name='VCC', side='right', anchorname='VCC')],
                      pinspacing=0.8, edgepadW=4.6, edgepadH=0.5, leadlen=0.4)

    sx = mcu.V33[0] - 9.5
    ir = sensor('SEN0206\nMLX90614 IR thermometer\nI²C addr 0x5A')
    d += ir.anchor('VCC').at((sx, mcu.V33[1] + 1.2))
    d += elm.Label().at((ir.center[0] - 0.7, ir.center[1])).label('SEN0206\nMLX90614\nIR thermometer\nI²C 0x5A', fontsize=10)
    wl = sensor('Grove Water Level 10 cm\nSS101020635\nI²C addr 0x77 + 0x78')
    d += wl.anchor('VCC').at((sx, ir.SCL[1] - 2.0))
    d += elm.Label().at((wl.center[0] - 0.7, wl.center[1])).label('Grove Water\nLevel 10 cm\nSS101020635\nI²C 0x77 + 0x78', fontsize=10)
    for s in (ir, wl):
        net(d, s.VCC, 'right', '3V3', 0.6)
        d += elm.Line().at(s.GND).right(0.6)
        d += elm.Ground()
        net(d, s.SDA, 'right', 'SDA', 0.6)
        net(d, s.SCL, 'right', 'SCL', 0.6)

    # ---------------- Pump driver (bottom left) ----------------
    by = wl.SCL[1] - 3.5
    mos = elm.Ic(pins=[elm.IcPin(name='VOUT−', side='right', anchorname='OUTn'),
                       elm.IcPin(name='VOUT+', side='right', anchorname='OUTp'),
                       elm.IcPin(name='VIN−', side='left', anchorname='INn'),
                       elm.IcPin(name='VIN+', side='left', anchorname='INp'),
                       elm.IcPin(name='GND', side='top', anchorname='CG'),
                       elm.IcPin(name='3V3', side='top', anchorname='CV'),
                       elm.IcPin(name='SIG', side='top', anchorname='CS')],
                 pinspacing=1.1, edgepadW=1.6, edgepadH=1.6, leadlen=0.5)
    d += mos.anchor('INp').at((sx + 2.5, by))
    d += elm.Label().at((mos.center[0], mos.center[1] - 2.5)).label('DFR0457 Gravity MOSFET', fontsize=10)
    net(d, mos.CS, 'up', 'PUMP_SIG', 0.5)
    net(d, mos.CV, 'up', '3V3', 0.5)
    d += elm.Line().at(mos.CG).up(0.5)
    d += elm.Ground().flip()

    d += elm.Line().at(mos.INp).left(1.2)
    p1 = d.here
    d += elm.SourceV().down().to((p1[0], mos.INn[1])).reverse().label('12 V 2 A\nplug pack', loc='top', ofst=0.3, fontsize=10)
    d += elm.Line().at(mos.INn).tox(p1[0])

    d += elm.Line().at(mos.OUTp).right(1.0)
    a = d.here
    d += elm.Line().right(2.6)
    top = d.here
    d += elm.Motor().down().to((top[0], mos.OUTn[1] - 1.2)).label('FIT0563\n12 V pump', loc='bottom', fontsize=10)
    bot = d.here
    d += elm.Line().tox(a[0])
    d += elm.Line().toy(mos.OUTn[1])
    d += elm.Line().tox(mos.OUTn[0])
    d += elm.Diode().at((a[0], a[1])).to((a[0], bot[1] + 0.0)).reverse().label('Schottky\n(band to +)', loc='bottom', fontsize=9)

    # ---------------- Audio (bottom right) ----------------
    ax = mcu.P25[0] + 1.0
    ay = by
    d += elm.Dot(open=True).at((ax, ay)).label('AUDIO', loc='left', fontsize=10, color='#1f4e9c')
    d += elm.Resistor().right(2.0).label('10 kΩ', fontsize=9)
    node = d.here
    d += elm.Dot()
    d.push()
    d += elm.Resistor().down(1.8).label('1 kΩ', fontsize=9, loc='bottom')
    d += elm.Ground()
    d.pop()
    amp = elm.Ic(pins=[elm.IcPin(name='IN−', side='left', anchorname='INn'),
                       elm.IcPin(name='IN+', side='left', anchorname='INp'),
                       elm.IcPin(name='OUT−', side='right', anchorname='On'),
                       elm.IcPin(name='OUT+', side='right', anchorname='Op'),
                       elm.IcPin(name='GND', side='top', anchorname='G'),
                       elm.IcPin(name='VIN', side='top', anchorname='V')],
                 pinspacing=1.0, edgepadW=1.4, edgepadH=1.6, leadlen=0.4)
    d += elm.Line().at(node).right(2.2)
    d += amp.anchor('INp')
    d += elm.Label().at((amp.center[0], amp.center[1] - 2.4)).label('PAM8302 2.5 W amplifier', fontsize=10)
    d += elm.Line().at(amp.INn).left(0.8)
    d += elm.Line().down(0.6)
    d += elm.Ground()
    net(d, amp.V, 'up', '3V3', 0.5)
    d += elm.Line().at(amp.G).up(0.5)
    d += elm.Ground().flip()
    d += elm.Line().at(amp.Op).right(0.8)
    sp = elm.Speaker().anchor('in1').label('8 Ω 5 W speaker', loc='top', fontsize=10)
    d += sp
    d += elm.Line().at(amp.On).tox(sp.in2[0] - 0.0).color('black')
    d += elm.Line().at((amp.On[0] + 0.8, amp.On[1])).toy(sp.in2[1])
    d += elm.Line().tox(sp.in2[0])

    d += elm.Label().at((mcu.center[0] + 2, by - 5.8)).label(
        'Nets with the same blue label are connected.  12 V reaches only the MOSFET output stage and the pump.\n'
        'Raspberry Pi 3B+ and Brio 100 webcam (own 5 V supply) talk to the FireBeetle over Bluetooth LE only.',
        fontsize=9)

    d.save(str(OUTPUT / 'schematic.svg'))
    d.save(str(OUTPUT / 'schematic.png'), dpi=200)
