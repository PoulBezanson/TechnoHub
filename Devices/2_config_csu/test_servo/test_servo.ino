#include <Servo.h>
#define PIN_SERVO_LEFT 53
#define PIN_SERVO_RIGHT 51

Servo servo_left;// создадим объект сервопривода
Servo servo_right;
int servo_init_left=0; // начальная позиция
int servo_init_right=180; // начальная позиция
int series=2;
int s=0;

void setup() {
  pinMode(PIN_SERVO_LEFT, OUTPUT);
  pinMode(PIN_SERVO_RIGHT, OUTPUT);
  digitalWrite(PIN_SERVO_LEFT,LOW);
  digitalWrite(PIN_SERVO_RIGHT,LOW);
  servo_left.attach(PIN_SERVO_LEFT);
  servo_right.attach(PIN_SERVO_RIGHT);
  
  servo_left.write(servo_init_left);
  servo_right.write(servo_init_right);
  // сервопривод на выводе 9
}

void loop() {
  
  while (s < series){
    for (int pos = 0; pos <= 100; pos += 1) { // от 0 до 180 градусов
      // шаг в один градус
      servo_left.write(pos);              // просим повернуться на позицию значения переменной 'pos'
      delay(100);                       // ждём 15ms для достижения позиции
    }
    servo_left.write(servo_init_left);
    
    for (int pos = 180; pos >= 80; pos -= 1) { // от 180 до 0 градусов
      servo_right.write(pos);              // просим повернуться на позицию значения переменной 'pos'
      delay(100);                       // ждём 15ms для достижения позиции
    }
    servo_right.write(servo_init_right);
    s+=1;
  }
}
