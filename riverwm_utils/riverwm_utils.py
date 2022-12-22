import sys
import os


def scan():
    this_dir = os.path.split(__file__)[0]
    protocol_dir = os.path.join(this_dir, '..', 'protocolV')
    input_files = ['wayland.xml',
                   'river-control-unstable-v1.xml',
                   'river-status-unstable-v1.xml']

    protocols = [Protocol.parse_file(os.path.join(protocol_dir, input_file))
                 for input_file in input_files]
    protocol_imports = {
        interface.name: protocol.name
        for protocol in protocols
        for interface in protocol.interface
    }

    pywayland_dir = os.path.split(pywayland.__file__)[0]
    output_dir = os.path.join(pywayland_dir, 'protocol')

    for protocol in protocols:
        protocol.output(output_dir, protocol_imports)


try:
    from pywayland.protocol.wayland import WlOutput
    from pywayland.protocol.wayland import WlSeat
    from pywayland.protocol.river_control_unstable_v1 import ZriverControlV1
    from pywayland.protocol.river_status_unstable_v1 import ZriverStatusManagerV1  # noqa: E501
except ModuleNotFoundError:
    try:
        from pywayland.scanner.protocol import Protocol
        import pywayland
        scan()
        print('Generated river bindings.')
        print('Please try running cycle-focused-tags again.')

    except Exception:
        this_dir = os.path.split(__file__)[0]
        protocol_dir = os.path.normpath(os.path.join(this_dir, '..', 'protocol'))
        ERROR_TEXT = (f'''
        Your pywayland package does not have bindings for river-control-unstable-v1
        and/or river-status-unstable-v1.

        An attempt was made to generate them but it failed. You may be able to
        generate the manually with the following command:

        python3 -m pywayland.scanner -i {protocol_dir}/wayland.xml '''
                  f'{protocol_dir}/river-control-unstable-v1.xml '
                  f'{protocol_dir}/river-status-unstable-v1.xml')

        print(ERROR_TEXT)

    sys.exit()

from pywayland.client import Display

STATUS_MANAGER = None
CONTROL = None

OUTPUTS = []
SEAT = None


class Output(object):
    def __init__(self):
        self.wl_output = None
        self.focused_tags = None
        self.status = None

    def destroy(self):
        if self.wl_output is not None:
            self.wl_output.destroy()
        if self.status is not None:
            self.status.destroy()

    def configure(self):
        self.status = STATUS_MANAGER.get_river_output_status(self.wl_output)
        self.status.user_data = self
        self.status.dispatcher["focused_tags"] = self.handle_focused_tags

    def handle_focused_tags(self, output_status, tags):
        self.focused_tags = tags


class Seat(object):
    def __init__(self):
        self.wl_seat = None
        self.status = None
        self.focused_output = None

    def destroy(self):
        if self.wl_seat is not None:
            self.wl_seat.destroy()

        if self.status is not None:
            self.status.destroy()

    def configure(self):
        self.status = STATUS_MANAGER.get_river_seat_status(self.wl_seat)
        self.status.user_data = self
        self.status.dispatcher["focused_output"] = self.handle_focused_output

    def handle_focused_output(self, _, wl_output):
        for output in OUTPUTS:
            if output.wl_output == wl_output:
                self.focused_output = output


def registry_handle_global(registry, id, interface, version):
    global STATUS_MANAGER
    global CONTROL
    global SEAT

    if interface == 'zriver_status_manager_v1':
        STATUS_MANAGER = registry.bind(id, ZriverStatusManagerV1, version)
    elif interface == 'zriver_control_v1':
        CONTROL = registry.bind(id, ZriverControlV1, version)
    elif interface == 'wl_output':
        output = Output()
        output.wl_output = registry.bind(id, WlOutput, version)
        OUTPUTS.append(output)
    elif interface == 'wl_seat':
        # We only care about the first seat
        if SEAT is None:
            SEAT = Seat()
            SEAT.wl_seat = registry.bind(id, WlSeat, version)


USAGE = '''usage: cycle-focused-tags [DIRECTION] [NTAGS]

Change to either the next or previous focused tags.

The DIRECTION argument shold be either 'next' or 'previous'.  The
NTAGS argument indicates at which tag number the cycling should loop
back to the first tag or to the last tag from the first tag.

If NTAGS is ommiteed, 32 is assumed if both arguments are ommitted
'next' is used as the DIRECTION.
'''


def cycle_focused_tags():
    n_tags = 32
    direction = 'next'

    if len(sys.argv) > 1:
        direction = sys.argv[1]

    if len(sys.argv) > 2:
        n_tags = int(sys.argv[2])

    if direction in ('-h', '--help'):
        print(USAGE)
        sys.exit(0)

    display = Display()
    display.connect()

    registry = display.get_registry()
    registry.dispatcher["global"] = registry_handle_global

    display.dispatch(block=True)
    display.roundtrip()

    if STATUS_MANAGER is None:
        print("Failed to bind river status manager")
        sys.exit()

    if CONTROL is None:
        print("Failed to bind river control")
        sys.exit()

    # Configuring all outputs, even the ones we do not care about,
    # should be faster than first waiting for river to advertise the
    # focused output of the SEAT.
    for output in OUTPUTS:
        output.configure()

    SEAT.configure()

    display.dispatch(block=True)
    display.roundtrip()
    tags = SEAT.focused_output.focused_tags
    new_tags = 0
    last_tag = 1 << (n_tags-1)
    if direction == 'next':
        # If last tag is set => unset it and set first bit on new_tags
        if (tags & last_tag) != 0:
            tags ^= last_tag
            new_tags = 1

        new_tags |= (tags << 1)

    else:
        # If lowest bit is set (first tag) => unset it and set
        # last_tag bit on new tags
        if (tags & 1) != 0:
            tags ^= 1
            new_tags = last_tag

        new_tags |= (tags >> 1)

    CONTROL.add_argument("set-focused-tags")
    CONTROL.add_argument(str(new_tags))
    CONTROL.run_command(SEAT.wl_seat)

    display.dispatch(block=True)
    display.roundtrip()

    SEAT.destroy()
    for output in OUTPUTS:
        output.destroy()

    if STATUS_MANAGER is not None:
        STATUS_MANAGER.destroy()

    if CONTROL is not None:
        CONTROL.destroy()

    display.disconnect()
