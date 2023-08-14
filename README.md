# Goniometric imaging software

GonioImsoft is a Python program designed to control
goniometric imaging experiments where

* rotary encoder values are read from a micro-controller (pySerial)
* analog voltage input/output controls light stimuli (nidaqmx)
* multiple cameras are controlled using MicroManager (pymmcore)

It was developed for the need of imaging 200 distinct
rotations (ie. eye locations) per specimen fast, requiring
only the spacebar to be pressed between the rotations.


## Required hardware and current limitations

Windows (and Linux to some extent) tested.

* A MicroManager-supported camera device
* National Instruments input/output board (NI specificity will be lifted
  in future)
* Serial device reporting rotation values in format "pos1,pos2\n" (an Arduino micro-controller, a default program provided)

For full description of the used hardware in a research setting,
please see
[the GHS-DPP imaging methods article](https://www.nature.com/articles/s42003-022-03142-0)


## How to install

### Rotary encoders

Rotary encoders (attached to their respective rotation stages)
monitor the rotation of the imaged specimen.
Their state is digitally read out using an Arduino microcontroller.

The default system uses 1024-step rotary encoders attached on
two perpendicular rotation stages.
To replicate this system, flash
`arduino/angle_sensors/angle_sensors.ino` and use the Arduino IDE's
Serial Monitor to confirm that everything works.

Different rotation encoders may require modifications to
the Arduino `ino` file. Each change in rotation should send
"pos1,pos2\n" (pos1 and pos2 are the absolute rotation steps
of the two encoders).


### Main software (using pip)

Requirements

* MicroManager and a working camera in it. Each camera needs a configuration file saved in the MicroManager directory.
* National Instrument input and output cards
* Python 3.6 or newer

Installing

```
pip install gonio-imsoft
```

## How to launch

```
python -m gonioimsoft.tui
```

