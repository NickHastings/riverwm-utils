'''Utilities for river wayland compositor'''
import sys
import os
import argparse
# pylint: disable=global-statement
try:
    from pywayland.protocol.wayland import WlOutput
    from pywayland.protocol.wayland import WlSeat
    from pywayland.protocol.river_control_unstable_v1 import ZriverControlV1
    from pywayland.protocol.river_status_unstable_v1 import ZriverStatusManagerV1  # noqa: E501
except ModuleNotFoundError:
    try:
        from pywayland.scanner.protocol import Protocol
        import pywayland
        this_dir = os.path.split(__file__)[0]
        protocol_dir = os.path.join(this_dir)
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
        print('Generated river bindings.')
        print('Please try running cycle-focused-tags again.')

    except ImportError:
        THIS_DIR = os.path.split(__file__)[0]
        PROTOCOL_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'protocol'))
        ERROR_TEXT = (f'''
        Your pywayland package does not have bindings for river-control-unstable-v1
        and/or river-status-unstable-v1.

        An attempt was made to generate them but it failed. You may be able to
        generate the manually with the following command:

        python3 -m pywayland.scanner -i {PROTOCOL_DIR}/wayland.xml '''
                      f'{PROTOCOL_DIR}/river-control-unstable-v1.xml '
                      f'{PROTOCOL_DIR}/river-status-unstable-v1.xml')

        print(ERROR_TEXT)

    sys.exit()

from pywayland.client import Display  # pylint: disable=import-error


STATUS_MANAGER = None
CONTROL = None

OUTPUTS = []
SEAT = None


class Output:
    '''Represents a wayland output a.k.a. a display'''
    def __init__(self):
        self.wl_output = None
        self.focused_tags = None
        self.tags = None
        self.status = None

    def destroy(self):
        '''Cleanup'''
        if self.wl_output is not None:
            self.wl_output.destroy()
        if self.status is not None:
            self.status.destroy()

    def configure(self):
        '''Setup'''
        self.status = STATUS_MANAGER.get_river_output_status(self.wl_output)
        self.status.user_data = self
        self.status.dispatcher["focused_tags"] = self.handle_focused_tags

    def handle_focused_tags(self, _, tags):
        '''Handle Event'''
        self.focused_tags = tags

class Seat:
    '''Represtents a wayland seat'''
    def __init__(self):
        self.wl_seat = None
        self.status = None
        self.focused_output = None

    def destroy(self):
        '''Cleanup'''
        if self.wl_seat is not None:
            self.wl_seat.destroy()

        if self.status is not None:
            self.status.destroy()

    def configure(self):
        '''Setup'''
        self.status = STATUS_MANAGER.get_river_seat_status(self.wl_seat)
        self.status.user_data = self
        self.status.dispatcher["focused_output"] = self.handle_focused_output

    def handle_focused_output(self, _, wl_output):
        '''Handle Event'''
        for output in OUTPUTS:
            if output.wl_output == wl_output:
                self.focused_output = output


def registry_handle_global(registry, wid, interface, version):
    '''Main Event Handler'''
    global STATUS_MANAGER
    global CONTROL
    global SEAT

    if interface == 'zriver_status_manager_v1':
        STATUS_MANAGER = registry.bind(wid, ZriverStatusManagerV1, version)
    elif interface == 'zriver_control_v1':
        CONTROL = registry.bind(wid, ZriverControlV1, version)
    elif interface == 'wl_output':
        output = Output()
        output.wl_output = registry.bind(wid, WlOutput, version)
        OUTPUTS.append(output)
    elif interface == 'wl_seat':
        # We only care about the first seat
        if SEAT is None:
            SEAT = Seat()
            SEAT.wl_seat = registry.bind(wid, WlSeat, version)

def check_direction(direction):
    '''Check validity of direction argument'''
    dir_char = direction[0].lower()
    if dir_char not in ('p', 'n'):
        raise argparse.ArgumentTypeError(f'Invalid direction: {direction}')

    return dir_char

def check_n_tags(n_tags):
    '''Check validity of direction argument'''
    i_n_tags = int(n_tags)
    if i_n_tags < 1 or 32 < i_n_tags:
        raise argparse.ArgumentTypeError(f'Invalid max number of tags: {n_tags}')

    return i_n_tags

def parse_command_line() -> argparse.Namespace:
    '''Read commanline arguments'''
    parser = argparse.ArgumentParser(
        description='Change to either the next or previous tags.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'direction', default='next', nargs='?', type=check_direction,
        help=('Direction to cycle through tags. Should be "next" or "previous".')
    )
    parser.add_argument(
        'n_tags', default=32, nargs='?', type=check_n_tags,
        help=('The tag number the cycling should loop back to the first tag or '
              'to the last tag from the first tag. Should be and integer '
              'between 1 and 32 inclusive.')
    )
    parser.add_argument(
        '--skip-unoccupied', '-s', action='store_true', default=False,
        help='Skip tags with no views.'
    )
    return parser.parse_args()

def cycle_focused_tags():
    '''Shift to next or previous tags'''
    args = parse_command_line()
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
    last_tag = 1 << (args.n_tags-1)
    if args.direction == 'n':
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
