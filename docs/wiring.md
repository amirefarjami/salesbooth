# Wiring — CHIZ Booth panel

## Buttons (8) → zero-delay USB encoder (shows up as a keyboard)

| Button | Place | Encoder key |
|---|---|---|
| 1 | left of the screen, top | `1` |
| 2 | right of the screen, top | `2` |
| 3 | left, middle | `3` |
| 4 | right, middle | `4` |
| 5 | left, bottom | `5` |
| 6 | right, bottom | `6` |
| Confirm (red, lit) | under the screen | `Enter` |
| Cancel «انصراف» | under the screen | `Esc` |

Keys can be changed in `booth.toml` → `[booth.keymap]`.
Each product button sits next to its card: button N always means the
N-th product (admin sort order). Only the first 6 active products are shown.

## Raspberry Pi GPIO (BCM numbering, all configurable in `booth.toml`)

| Part | GPIO | Notes |
|---|---|---|
| Showcase lock relay | 17 (`lock_gpio`) | 12 V solenoid through a relay; ON = unlocked |
| Door sensor (reed switch) | 27 (`door_sensor_gpio`) | switch between pin and GND, internal pull-up; door shut = LOW |
| Red button lamp | 22 (`red_light_gpio`) | through a transistor/relay if the lamp is 12 V |
| MOSFET 1 — booth main light | 12 (`booth_light_gpio`) | PWM-dimmed (logic-level MOSFET, e.g. IRLZ44N) |
| MOSFET 2 — red warning lights | 13 (`warn_light_gpio`) | on during the last seconds and any overtime |
| WS2812B LED strip | 18 (`led_gpio`) | data line; needs root (rpi_ws281x) |

## Hand-over sequence (semi-automatic — an operator is always there)

1. Payment approved → success animation on the screen.
2. Lock relay ON: the screen says «در ویترین رو باز کن و خریدت رو بردار»
   and lists the items (with the order code); the operator watches.
3. Door sensor sees the door open → relay OFF (the latch catches again on
   closing) and the countdown starts: 20 s for one item, +5 s for every
   extra item (`door_open_s`, `door_extra_per_item_s`). The ring empties
   from 12 o'clock counter-clockwise (RTL).
4. Last 5 s (`door_warn_s`): beep-beep every second, MOSFET 1 dims the
   booth light, MOSFET 2 turns the red lights on. After the countdown this
   keeps going until the door is shut.
5. Door shut → order marked delivered, back to the attract screen.
   Door never opened within `door_wait_s` → lock again; the operator can
   mark the order delivered in the admin panel.

Card-reader payments are automatic: the booth pushes the amount to the
reader, the buyer only swipes and enters the PIN, and the reader reports the
result back (`core/pos.py`). The wire protocol depends on the PSP's PC-POS
spec, so the real driver is added once the device is chosen (TASKS #24);
until then `pos_driver = "sim"` approves after `pos_sim_approve_s` seconds.

## Field check

`make factory-test` shows every button press, the door sensor state, and
on the red button lights its lamp and pulses the lock relay for 1 s.
On the laptop simulator the `d` key opens/closes the door.
