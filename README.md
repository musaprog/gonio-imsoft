# Goniometric imaging software

GonioImsoft is a terminal user interface Python program
designed to control the
goniometric high-speed imaging experiments where

* rotary encoder values are read over serial (pySerial)
* NI-DAQmx is used for general input/output (nidaqmx)
* the camera is controlled over MicroManager (pymmcore)

It was developed for the need of imaging 200 distinct
rotations (eye locations) per specimen fast, requiring
only the space bar to be pressed between the rotations.

For general imaging, without these specific needs,
it is better to use MicroManager or other image
acquisition software.

Following block diagram illustrates the used software architecture

´´´
tui.py - GonioImsoft terminal user interface
  |
core.py
  |
  |__ nidaqmx - Control NI boards (trigger, stimuli)
  |
  |__ pyserial - Read Arduino (rotation data)
  |
  |__ Camera Client
        |_Camera Server
	    |
	    |__ pymmcore - camera control using MicroManager
	    |__ tifffile - writes images/stacks
´´´

Thanks to the camera server/client model,
the cameras can be ran on separate computers.
This parallel image acquisition allows using many cameras
without worrying about memory and bandwidth or processing
limits.



## Required hardware and current limitations

Windows (and Linux to some extent) tested.

* A MicroManager-supported camera device
* National Instruments input/output board (NI specificity can be
  lifted in future by using PyVISA or similar)
* Serial device reporting rotation values in format "pos1,pos2\n"

For full description of the used hardware configuration,
please see
[the GHS-DPP imaging methods article](https://www.nature.com/articles/s42003-022-03142-0)


## How to install


### Rotary encoders

Rotary encoders monitor the rotation of the imaged specimen/sample.
They are
mechanically attached to their respective rotation stages.
Their state is digitally read out using an Arduino microcontroller.

In our system, we used two 1024-step rotary encoders attached on
two perpendicular rotation stages.
If your system is identical, you can flash 
`arduino/angle_sensors/angle_sensors.ino` and use the Serial Monitor
in the Arduino IDE to confirm it works.

If your system differs, you may have to modify the Arduino `ino` file.
However, any serial device reporting rotations in format "pos1,pos2\n"
will do. Here, pos1 and pos2 are rotation steps (integers)
of the two encoders.


### Main software (using pip)

First please make sure that you have
* MicroManager installation with a working camera
* National Insturments cards configured with
names *Dev1* and *Dev2* for input and output, respectively
* Python 3.6 or newer

Then, use pip to install

```
pip install gonio-imsoft
```

## How to use

You can launch the main program using

```
python -m gonioimsoft.tui
```


