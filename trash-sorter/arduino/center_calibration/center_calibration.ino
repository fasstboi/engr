#include <Servo.h>
#include <stdlib.h>
#include <string.h>
Servo servo;
const int LOW_US = 1300, HIGH_US = 1700;
int currentUs = 1500, targetUs = 1500;
bool moving = false;
unsigned long lastStep = 0;
char buffer[24];
byte used = 0;
bool overflowed = false;

void command(char *line) {
  if (!strcmp(line, "PING")) { Serial.println("CAL_PONG"); return; }
  if (strncmp(line, "SET ", 4)) { Serial.println("INVALID"); return; }
  if (moving) { Serial.println("BUSY"); return; }
  // Require digits only, no suffix or sign.
  char *number = line + 4;
  if (!*number || strlen(number) > 4) { Serial.println("INVALID"); return; }
  for (char *p = number; *p; ++p) {
    if (*p < '0' || *p > '9') { Serial.println("INVALID"); return; }
  }
  int value = atoi(number);
  if (value < LOW_US || value > HIGH_US) { Serial.println("RANGE"); return; }
  targetUs = value;
  moving = true;
  lastStep = millis();
}

void setup() {
  Serial.begin(115200);
  servo.attach(9, 500, 2500);
  servo.writeMicroseconds(1500);
  Serial.println("CAL_READY");
}

void loop() {
  for (byte count = 0; count < 32 && Serial.available(); ++count) {
    char ch = Serial.read();
    if (ch == '\n') {
      buffer[used] = '\0';
      if (overflowed) Serial.println("INVALID"); else command(buffer);
      used = 0; overflowed = false;
    } else if (ch != '\r') {
      if (used < sizeof(buffer) - 1) buffer[used++] = ch;
      else overflowed = true;
    }
  }
  if (moving && millis() - lastStep >= 10) {
    lastStep = millis();
    if (currentUs < targetUs) ++currentUs;
    else if (currentUs > targetUs) --currentUs;
    servo.writeMicroseconds(currentUs);
    if (currentUs == targetUs) {
      moving = false;
      Serial.print("CAL_DONE "); Serial.println(currentUs);
    }
  }
}
