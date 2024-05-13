'''Utilities for river wayland compositor'''
import sys
import os
import argparse
import struct
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

        protocols = [Protocol.parse_file(os.path.join(
            protocol_dir, input_file)) for input_file in input_files]
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
        PROTOCOL_DIR = os.path.normpath(
            os.path.join(THIS_DIR, '..', 'protocol'))
        ERROR_TEXT = (f'''
        Your pywayland package does not have bindings for
        river-control-unstable-v1 and/or river-status-unstable-v1.

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
        self.view_tags = None
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
        self.status.dispatcher["view_tags"] = self.handle_view_tags

    def handle_focused_tags(self, _, tags):
        '''Handle Event'''
        self.focused_tags = tags

    def handle_view_tags(self, _, tags):
        '''Handle Event'''
        self.view_tags = tags


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


def prepare_display(display: Display):
    '''Prepare display global objects'''
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


def close_display(display: Display):
    '''Clean up objects'''
    SEAT.destroy()
    for output in OUTPUTS:
        output.destroy()

    if STATUS_MANAGER is not None:
        STATUS_MANAGER.destroy()

    if CONTROL is not None:
        CONTROL.destroy()

    display.disconnect()


def check_direction(direction: str) -> str:
    '''Check validity of direction argument'''
    dir_char = direction[0].lower()
    if dir_char not in ('p', 'n'):
        raise argparse.ArgumentTypeError(f'Invalid direction: {direction}')

    return dir_char


def check_n_tags(n_tags: int) -> int:
    '''Check validity of direction argument'''
    i_n_tags = int(n_tags)
    if i_n_tags < 1 or 32 < i_n_tags:
        raise argparse.ArgumentTypeError(
            f'Invalid max number of tags: {n_tags}')

    return i_n_tags


def parse_command_line() -> argparse.Namespace:
    '''Read commanline arguments'''
    parser = argparse.ArgumentParser(
        description='Change to either the next or previous tags.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'direction', default='next', nargs='?', type=check_direction,
        help=('Direction to cycle through tags. Either "next" or "previous".')
    )
    parser.add_argument(
        'n_tags', default=32, nargs='?', type=check_n_tags,
        help=('The tag number the cycling should loop back to the first tag '
              'or to the last tag from the first tag. Should be and integer '
              'between 1 and 32 inclusive.')
    )
    parser.add_argument(
        '--all-outputs', '-a', dest='all_outputs', action='store_true',
        help='Cycle the tags for all outputs (following the active output).'
    )
    parser.add_argument(
        '--follow', '-f', dest='follow', action='store_true',
        help='Move the active window when cycling.'
    )
    parser.add_argument(
        '--skip-occupied', '-o', action='store_true',
        help='Skip occupied tags.'
    )
    parser.add_argument(
        '--skip-empty', '-s', action='store_true',
        help='Skip empty tags.'
    )
    parser.add_argument(
        '--debug', '-d', action='store_true',
        help='Enable debugging output.'
    )
    return parser.parse_args()


def get_occupied_tags(cli_args: argparse.Namespace) -> int:
    '''Return bitmap of occupied tags as int'''
    used_tags = (1 << cli_args.n_tags) - 1

    if not cli_args.all_outputs or len(OUTPUTS) == 1:
        return get_occupied_from_view_tags(
            SEAT.focused_output.view_tags) & used_tags

    occupied_tags = 0
    for output in OUTPUTS:
        occupied_tags |= get_occupied_from_view_tags(output.view_tags)

    return occupied_tags & used_tags


def get_occupied_from_view_tags(view_tags: int):
    '''Return bitmap of view_tags occupied tags as int'''
    occupied_tags = 0
    nviews = int(len(view_tags) / 4)
    for view in struct.unpack(f'{nviews}I', view_tags):
        occupied_tags |= view

    return occupied_tags


def get_new_tags(cli_args: argparse.Namespace,
                 occupied_tags: int) -> int:
    '''Return the new tag set'''
    used_tags = (1 << cli_args.n_tags) - 1
    tags = SEAT.focused_output.focused_tags & used_tags

    # All tags are empty and we want to skip empty tags
    # => return the current tags
    if cli_args.skip_empty and occupied_tags == 0:
        return tags

    # All tags are occupied and we want to skip occupied tags
    # => return the current tags
    if cli_args.skip_occupied and used_tags == (used_tags ^ occupied_tags):
        return tags

    i = 0
    initial_tags = tags
    last_tag = 1 << (cli_args.n_tags - 1)
    while True:
        if i >= cli_args.n_tags:
            # Looped over all tags. Something is wrong, bail out
            print('Warning looped over all tags')
            return initial_tags

        new_tags = 0
        if cli_args.direction == 'n':
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

        tags = new_tags
        i += 1

        if cli_args.skip_empty and not bool(tags & occupied_tags):
            continue

        if cli_args.skip_occupied and bool(tags & occupied_tags):
            continue

        return tags


def set_new_tags(cli_args: argparse.Namespace, new_tags: int):
    '''Set the focussed tags'''
    if cli_args.follow:
        CONTROL.add_argument("set-view-tags")
        CONTROL.add_argument(str(new_tags))
        CONTROL.run_command(SEAT.wl_seat)

    CONTROL.add_argument("set-focused-tags")
    CONTROL.add_argument(str(new_tags))
    CONTROL.run_command(SEAT.wl_seat)

    if len(OUTPUTS) == 1 or not cli_args.all_outputs:
        return

    # The active output has been switched, walk over all other outputs and
    # set their tags too, wrapping back to the start (where setting can be
    # skipped).
    for i in range(len(OUTPUTS)):
        CONTROL.add_argument("focus-output")
        CONTROL.add_argument("next")
        CONTROL.run_command(SEAT.wl_seat)

        if i + 1 == len(OUTPUTS):
            # Back to the start which has already had it's tags set.
            # Breaking here isn't needed but the next assignment is
            # redundant.
            break

        CONTROL.add_argument("set-focused-tags")
        CONTROL.add_argument(str(new_tags))
        CONTROL.run_command(SEAT.wl_seat)

    return


def cycle_focused_tags():
    '''Shift to next or previous tags'''
    args = parse_command_line()
    display = Display()
    prepare_display(display)

    occupied_tags = get_occupied_tags(args)
    new_tags = get_new_tags(args, occupied_tags)

    if args.debug:
        print(f'cur 0b{SEAT.focused_output.focused_tags:032b}')
        print(f'occ 0b{occupied_tags:032b}')
        print(f'new 0b{new_tags:032b}')

    set_new_tags(args, new_tags)

    display.dispatch(block=True)
    display.roundtrip()

    close_display(display)
