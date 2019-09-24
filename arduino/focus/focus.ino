/*
Writing with digital pins to control the microcope focus
through a stepper motor.
*/

int pin_closer = 13;
int pin_further = 12;


int get_action()
{
	if(Serial.available() > 0)
	{
		return Serial.read();
	}
	else
	{
		return 0;
	}
}


void setup()
{
	Serial.begin(9600);
	pinMode(pin_closer, OUTPUT);
	pinMode(pin_further, OUTPUT);

	digitalWrite(pin_closer, LOW);
	digitalWrite(pin_further, LOW);
}


void loop()
{
	if(get_action == "c")
	{
		digitalWrite(pin_closer, 'HIGH')
		delay(100)
		digitalWrite(pin_closer, 'LOW')
	}
	else if(get_action == 'f')
	{
		digitalWrite(pin_further, 'HIGH')
		delay(100)
		digitalWrite(pin_further, 'LOW')
	}
}
