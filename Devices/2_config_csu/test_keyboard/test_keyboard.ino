//Тест клавиатуры
//При нажатии на клавишу загорается диод:
//'1' - красный
//'2' - желтый
//'3' - зеленый
//'4' - гаснут все диоды
#include <SimpleKeypad.h>

// Инициализация клавиатуры
#define KP_ROWS 1 // размеры клавиатуры
#define KP_COLS 4 // размеры клавиатуры
byte colPins[KP_COLS] = {39, 37,  33, 41}; // Порты подключения к клавиатуре
byte rowPins[KP_ROWS] = {35}; // GND для клавиатуры
char keys[KP_ROWS][KP_COLS] = {{'1', '2', '3', '4'}}; // Массив имён кнопок
SimpleKeypad pad((char*)keys, rowPins, colPins, KP_ROWS, KP_COLS);  // Объект для работы с клавиатурой
//

enum{ // Состояния диодов
  RYG, RXX, XYX, XXG, XXX
} DiodeState;

void setup() {
    // инициализация пинов диодов
  pinMode(47, OUTPUT); // желтый диод
  pinMode(45, OUTPUT); // зеленый диод
  pinMode(43, OUTPUT); // красный диод
  
  // проверка отсветки диодов
  SetDiodColor(RYG);
  delay(1000);
  SetDiodColor(XXX);
}

void loop() {
  //  Обработка нажатия кнопки
  char key = pad.getKey();  // Проверка нажатия кнопки
  if(key)  
    handlerKey(key);
}

inline __attribute__((always_inline)) void handlerKey(char key){
   switch(key){
     case '1': // Включение красного диода
       SetDiodColor(RXX);
     break;
     case '2': // Включение желтого диода
       SetDiodColor(XYX);
     break;
     case '3': // Включение зеленого диода
       SetDiodColor(XXG);
     break;
     case '4': // Выключение всех диодов
       SetDiodColor(XXX);
     break;
   }    
  delay(100);
  
}

// Установка заданной комбинации отсветки светодиодов
void SetDiodColor(int diode)
{
  switch (diode)
  {
    case RYG: // горят красный, желтый, зеленый
      digitalWrite(43, HIGH);
      digitalWrite(47, HIGH);
      digitalWrite(45, HIGH);
      break;
    case RXX: // горит красный
      digitalWrite(43, HIGH);
      digitalWrite(47, LOW);
      digitalWrite(45, LOW);
    break;
    case XYX: // горит желтый
      digitalWrite(43, LOW);
      digitalWrite(47, HIGH);
      digitalWrite(45, LOW);
    break;
    case XXG: // горит зеленый
      digitalWrite(43, LOW);
      digitalWrite(47, LOW);
      digitalWrite(45, HIGH);
    break;
    case XXX: // ничего не горит
      digitalWrite(43, LOW);
      digitalWrite(47, LOW);
      digitalWrite(45, LOW);
    break;
  }
}

