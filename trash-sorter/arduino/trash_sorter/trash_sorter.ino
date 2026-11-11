#include <Servo.h>
#include <string.h>

// MS24-F near-vertical targets, assuming direct linkage and level center.
// Nominal 270 degrees over 500-2500 us: +/-556 us is approximately +/-75 degrees.
// Actual tray angles depend on servo calibration and mechanical linkage.
const byte SERVO_PIN = 9;
const int MIN_US = 500, MAX_US = 2500;
const int CENTER_US = 1500, LEFT_US = 944, RIGHT_US = 2056;
const unsigned long HOLD_MS = 1500;
const unsigned long STEP_MS = 10;
const int STEP_US = 5;  // Gentle 556 us move takes about 1.12 seconds per direction.
const unsigned long CENTER_SETTLE_MS = 300;
static_assert(LEFT_US >= MIN_US && LEFT_US <= MAX_US, "LEFT out of range");
static_assert(RIGHT_US >= MIN_US && RIGHT_US <= MAX_US, "RIGHT out of range");
static_assert(CENTER_US >= MIN_US && CENTER_US <= MAX_US, "CENTER out of range");

Servo servo;
enum State { IDLE, TILTING, HOLDING, RETURNING, SETTLING };
State state = SETTLING;
int currentUs = CENTER_US, targetUs = CENTER_US;
unsigned long changedAt = 0, lastStep = 0;
bool booting = true;
char buffer[24];
byte used = 0;
bool overflowed = false;

void handleCommand(const char *command) {
  if (!strcmp(command, "PING")) {
    Serial.println(state == IDLE ? "PONG" : "BUSY");
    return;
  }
  if (strcmp(command, "LEFT") && strcmp(command, "RIGHT") && strcmp(command, "CENTER")) {
    Serial.println("INVALID");  // No movement for malformed commands.
    return;
  }
  if (state != IDLE) { Serial.println("BUSY"); return; }
  Serial.print("ACK "); Serial.println(command);
  changedAt = lastStep = millis();
  if (!strcmp(command, "CENTER")) {
    servo.writeMicroseconds(CENTER_US);
    currentUs = CENTER_US;
    state = SETTLING;
  } else {
    targetUs = !strcmp(command, "LEFT") ? LEFT_US : RIGHT_US;
    state = TILTING;
  }
}

void setup() {
  Serial.begin(115200);
  servo.attach(9, 500, 2500);
  servo.writeMicroseconds(CENTER_US);
  changedAt = millis();
}

void loop() {
  // Bounded parsing; discard overlong lines rather than acting on a prefix.
  for (byte count = 0; count < 32 && Serial.available(); ++count) {
    char ch = Serial.read();
    if (ch == '\n') {
      buffer[used] = '\0';
      if (overflowed) Serial.println("INVALID");
      else handleCommand(buffer);
      used = 0; overflowed = false;
    } else if (ch != '\r') {
      if (used < sizeof(buffer) - 1) buffer[used++] = ch;
      else overflowed = true;
    }
  }
  unsigned long now = millis();
  if ((state == TILTING || state == RETURNING) && now - lastStep >= STEP_MS) {
    lastStep = now;
    int delta = targetUs - currentUs;
    if (delta > STEP_US) delta = STEP_US;
    if (delta < -STEP_US) delta = -STEP_US;
    currentUs += delta;
    servo.writeMicroseconds(currentUs);
    if (currentUs == targetUs) {
      state = state == TILTING ? HOLDING : SETTLING;
      changedAt = now;
    }
  } else if (state == HOLDING && now - changedAt >= HOLD_MS) {
    targetUs = CENTER_US;
    state = RETURNING;
    lastStep = now;
  } else if (state == SETTLING && now - changedAt >= CENTER_SETTLE_MS) {
    state = IDLE;
    if (booting) { booting = false; Serial.println("READY"); }
    else Serial.println("DONE");
  }
}
