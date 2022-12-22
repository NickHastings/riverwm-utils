# riverwm-utils
Utilities for the River Wayland compositor. Currently just one utility is included.

## Usage

### cycle-focused-tags

Change to either the next or previous focused tags.

As can be seen in a [pull
request](https://github.com/riverwm/river/pull/506), this
functionality can easily be built directly into river. However, [as
explained by Leon
Plickat](https://github.com/riverwm/river/pull/506#issuecomment-1008021752)
there is a plan to separate the window management to a separate
client, and as such new additions are not being accepted. The
approach implemented here was suggested and sample code was
provided. That sample code forms the basis of this script.

The script takes two arguments: the first is being the direction
next|previous, the second being the maximum number of tags at which
the cycling should wrap back to the first tag (or to the last tag from
the first tag). 

If the second argument is omitted the maximum number of tags is
assumed to be 32.  If both arguments are ommited the direction,
next, will be used.

The script can be called using spawn in the users init file. For example:
```
riverctl map normal Mod4 Up spawn "cycle-focused-tags previous 9"
riverctl map normal Mod4 Down spawn "cycle-focused-tags next 9"
```


## Install

### Development version
Clone the repository:
```
git clone https://github.com/NickHastings/riverwm-utils.git
```
Install locally with pip
```
python3 -m pip install ./riverwm-utils
```
### Stable realeases
```
python3 -m pip install riverwm-utils
```

### Wayland protocols and pywayland

For `cycle-focused-tags` to work the relevant wayland protocol xml
files will need to be scanned by pywayland. If this has not already
been done `cycle-focused-tags` will attempt to do so.

## Licensing

riverwm-utils is released under the GNU General Public License v3.0 only.

The protocols in the `protocol` directory are released under various licenses by
various parties. You should refer to the copyright block of each protocol for
the licensing information.
