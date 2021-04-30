

import matplotlib.pyplot as plt
from pupil_imsoft.imaging_nidaq_stimulus import get_pulse_stimulus


stim, ill, cam = get_pulse_stimulus(0.2, 0.1, 0.1, 0.01, 10, 3, 1000)


plt.plot(stim)
plt.plot(ill)
plt.plot(cam)
plt.show()
