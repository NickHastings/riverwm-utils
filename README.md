# riverwm-utils
Utilities for the River Wayland compositor. Currently just one utility is included.
description = 

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

## Usage

# cycle-focused-tags
The script takes two arguments: the first being the direction next|previous, the second being the maximum number of tags at which the cycling should wrap back to the first tag (or to the last tag from the first tag).
The script can be called using spawn in the users init file. For example:
```
riverctl map normal Mod4 Up spawn "cycle-focused-tags previous 9"
riverctl map normal Mod4 Down spawn "cycle-focused-tags next 9"
```
