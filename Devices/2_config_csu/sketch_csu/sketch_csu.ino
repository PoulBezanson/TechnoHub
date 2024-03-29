#include <math.h>
#include <Servo.h>
#include <ModbusRtu.h>
//#include <Keypad.h>
#include <SimpleKeypad.h>
#include <LCD_1602_RUS.h>
#include <MPU6050.h>
#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include <I2Cdev.h>

// Инициализация параметров управления
int control_period = 10; // Период цикла управления по умолчанию (мс)
unsigned long oldTimeStabilisation = 0; // Время начала предыдущего цикла управления
unsigned long periodStabilisation = 0;  // Действительное значение цикла управления
unsigned long oldMenuTime = 0;  // Время нахождения макета неподвижно
unsigned long start_time = 0;  // Время запуска СУД
unsigned long duration_time = 0; //  Длительность эксперимента по умолчанию (сек.)
#define DEFAULT_DURATION_TIME 20; // длительность эксперимента (секунды)
long control_value = 0; // значение управляющего воздействия для алгоритма 1
long linearStabAngle = 0; // значение управляющего воздействия для алгоритма 2
int index_pid = 1; // Код выбранного набора ПИД коэффициентов (0 - внешний набор из контроллера эксперимента)/ Максимум - N_PIDS
boolean is_local_mode=true; // признак локального управления, иначе - дистанционное
#define N_PIDS 6 //количество наборов коэффициентов ПИД  регулятора
int pid_decimals[6]={0,  3,  1, 2, 7, 0}; // размер десятичной части коэффициентов ПИД регулятора
// коэффициенты ПИД регулятора в последовательности {kPangle, kIangle, kDangle, kPlinear, kIlinear, kDlinear}
double pid_value[N_PIDS][6]={{0, 0, 0, 0, 0, 0},
                              {5, 15,  35, 1, 0,  8},
                              {5, 15,  35,  3,  0,  8},
                              {5, 15,  35,  5,  0,  8},
                              {7, 15,  35,  3,  0,  8},
                              {7, 15,  35,  3,  1,  8}}; 
//
// Инициализация физических параметров установки
#define R 3.17  // Радиус колеса
//
// Инициализация системы вертикализации
#define PIN_SERVO_LEFT 53
#define PIN_SERVO_RIGHT 51
Servo servo_left;// создадим объект сервопривода
Servo servo_right;
int servo_init_left=1; // начальная позиция
int servo_init_right=179; // начальная позиция
int Ang; // значение текущего угла сервопривода
int dAng=0; // значение приращения угла вертикализации (+1 или -1)
//
// Инициализация портов управления двигателями
#define MOTOR_A 6
#define MOTOR_B 7
#define MIN_POWER 70  // Минимальное управляющее воздействие, которое подается на двигатели
//                          
// инициализация акселерометра горизонтирования (уровня)
#define G 16384 // Ускорение свободного падения для акселерометра при диапазоне +-2g
#define horizontErr (-10) // Калибровочная поправка аксилирометра было 97
#define COUNT 5000  // Количество значений для горизонтирования
MPU6050 mpu;  // Объект для работы с акселерометром
double tmpBias = 0; // значение поправки целевого угла по результатам калибровки
//
// Инициализация клавиатуры
#define KP_ROWS 1 // размеры клавиатуры
#define KP_COLS 4 // размеры клавиатуры
byte colPins[KP_COLS] = {39, 37,  33, 41}; // Порты подключения к клавиатуре
byte rowPins[KP_ROWS] = {35}; // GND для клавиатуры
char keys[KP_ROWS][KP_COLS] = {{'1', '2', '3', '4'}}; // Массив имён кнопок
SimpleKeypad pad((char*)keys, rowPins, colPins, KP_ROWS, KP_COLS);  // Объект для работы с клавиатурой
//
// Инициализация modbus шины
#define HOLDING_SIZE 13 // Количество каналов для OPC сервера
#define ID 100      // Адрес МК для обмена данными с ОРС сервером
Modbus slave(ID, 0, 0);  // Объект для работы с ОРС сервером
uint16_t holding[HOLDING_SIZE]; // modbus регистры
int holding_decimals[HOLDING_SIZE]={0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0};
// указатели на регистры
uint16_t *p_angle=holding;               // адрес согласовать с result_manifest.yaml
uint16_t *p_angle_speed=holding+1;       // адрес согласовать с result_manifest.yaml
uint16_t *p_angle_integral=holding+2;    // адрес согласовать с result_manifest.yaml
uint16_t *p_position=holding+3;          // адрес согласовать с result_manifest.yaml
uint16_t *p_position_speed=holding+4;    // адрес согласовать с result_manifest.yaml
uint16_t *p_position_integral=holding+5; // адрес согласовать с result_manifest.yaml
uint16_t *p_control_value=holding+6;     // адрес согласовать с result_manifest.yaml
uint16_t *p_is_local_mode=holding+7;     // адрес согласовать с experiment_manifest.yaml
uint16_t *p_fix_claim_id=holding+8;      // адрес согласовать с experiment_manifest.yaml
uint16_t *p_initional_flag=holding+9;    // адрес согласовать с experiment_manifest.yaml
uint16_t *p_duration_time=holding+10;    // адрес согласовать с option_manifest.yaml
uint16_t *p_delta_angle_bias=holding+11;  // адрес согласовать с option_manifest.yaml
uint16_t *p_index_pid=holding+12;        // адрес согласовать с option_manifest.yaml

// указатели decimals регистров
int *p_delta_angle_bias_decimals=holding_decimals+11;
//
// инициализация датчика линейного положения объекта
int EncoderPinMSB1 = 2; //пин датчика углового положение колеса //MSB = most significant bit
int EncoderPinLSB1 = 3; //пин датчика углового положение колеса //LSB = least significant bit  
volatile int lastEncoded1 = 0;
volatile int EncoderValue1 = 0; // начальное значение показания энкодера датчика углового положение колеса (имп)
volatile int prevEncoderValue1 = 0; // предыдущее значение показания энкодера датчика углового положение колеса (имп)
volatile double AngleValue1 = 0; // значение показания энкодера датчика углового положение колеса (гр)
int criticalLinear = 1313; // Критическое линейное смещение по умолчанию соответствует 20 см.
int linear_bias = 0;  // Целевое линейное положение
int linear_err_limit; // Допустимое значение линейного отклонения перед вертикализацией
int linear_err; // Текущая ошибка линейного отклонения перед вертикализацией
//
// инициализация датчика углового положения объекта
int EncoderPinMSB2 = 19; //пин датчика углового положение ОУ //MSB = most significant bit
int EncoderPinLSB2 = 18; //пин датчика углового положение ОУ //LSB = least significant bit  
volatile int lastEncoded2 = 0; 
volatile int EncoderValue2 = 0; // значение показания энкодера датчика углового положение ОУ (имп)
volatile int prevEncoderValue2 = 0; // предыдущее значение показания инкодера датчика углового положение ОУ (имп)
volatile double AngleValue2 = 0; // значение показания энкодера датчика углового положение ОУ (гр)
int criticalAngle = 150;  // Критическое угловое отклонение по умолчанию соответствует 6.75 гр.
#define DEFAULT_BIAS 1949 // Целевое значение углового положения относительно платформы
int angle_bias = DEFAULT_BIAS;  // Целевое угловое положение
#define DEFAULT_DELTA_ANGLE  0.675 // Отклонение от целевого углового положения при вертикализации (град.)
int delta_angle_bias=(int) (DEFAULT_DELTA_ANGLE*22.22); //Преобразование угла в количество импульсов
//
// Инициализация LCD дисплея
LCD_1602_RUS LCD(0x27, 16, 2);  // Объект для вывода информации на дисплей
int maxLinear = 0;  // Максимально достигнутое смещение для отображения
int maxAngle = 0;  // Максимально достигнутое угловое отклонение для отображения 
int prevMaxLinear = 0;  // Предыдущее максимально достигнутое смещение для отображения
int prevMaxAngle = 0;  // Предыдущее максимально достигнутое угловое отклонение для отображения
//

// Инициализация ПИД коэффициентов
double kPangle = 0;  // Пропорциональный коэффициент ПИД2
double kIangle = 0; // Интегральный коэффициент ПИД2 
double kDangle = 0; // Дифференциальный коэффициент ПИД2

double kPlinear = 0; // Пропорциональный коэффициент ПИД1
double kIlinear = 0; // Интегральный коэффициент ПИД1
double kDlinear = 0; // Дифференциальный коэффициент ПИД1

double kPangle2 = 0;  // Пропорциональный коэффициент ПИД2
double kIangle2 = 0; // Интегральный коэффициент ПИД2 
double kDangle2 = 0; // Дифференциальный коэффициент ПИД2

double kPlinear2 = 0; // Пропорциональный коэффициент ПИД1
double kIlinear2 = 0; // Интегральный коэффициент ПИД1
double kDlinear2 = 0; // Дифференциальный коэффициент ПИД1

// Инициализация параметров движение
long  old_position = 0;
long  my_position_integral = 0;
long  old_angle = 0;
long  my_angle_integral = 0;

//инициализация исходной информации модели для регулятора 2
float Ae[2][2] = { -0.364912, 0.053954, -4.178116, 0.584912}; 
float He[2][2] = { -163.798085, 0.000018, -745.016628, 0.000055}; 
float Be[2] = { -0.000442, 0.003398}; 
float H[2][2] = {136.610714, -0.000013, 417.491017, 0}; 
float S[4] = { -1533, -252, -460 - 495};

//инициализация начальной информации для регулятора 2
float Xa[2] = {0, 0}; 
float Va[2] = {0, 0}; 
float X[4] = {0, 0, 0, 0}; 
float Y[2] = {0, 0}; 
volatile int U = 0; 

enum{ // Режимы установки
  CALIBRATION, READY, STABILISATION, FALLED
} State;

enum{ // Состояния диодов
  RYG, RXX, XYX, XXG, XXX
} DiodeState;

enum{ // Режим отображения дисплея
  OPTIONS, MENU, MAXVALUES
} DisplayMode;


long computePIDangle(int input, int setpoint, double kp, double ki, double kd, unsigned long dt);
long computePIDlinear(int input, int setpoint, double kp, double ki, double kd, unsigned long dt);


void setup() {
  slave.begin(19200);
  TCCR4A = 0b00000011;  // Переключение ШИМ в разрешение 10 бит
  
  // перевод системы вертикализации в начальное состояние
  pinMode(PIN_SERVO_LEFT, OUTPUT);
  pinMode(PIN_SERVO_RIGHT, OUTPUT);
  digitalWrite(PIN_SERVO_LEFT,LOW);
  digitalWrite(PIN_SERVO_RIGHT,LOW);
  servo_left.attach(PIN_SERVO_LEFT);
  servo_right.attach(PIN_SERVO_RIGHT);
  servo_left.write(servo_init_left);
  servo_right.write(servo_init_right);
    
  // инициализация пинов диодов
  pinMode(47, OUTPUT); // желтый диод
  pinMode(45, OUTPUT); // зеленый диод
  pinMode(43, OUTPUT); // красный диод
  
  // проверка отсветки диодов
  SetDiodColor(RYG);
  
  // Включение акселерометра
  pinMode(14, OUTPUT);
  pinMode(15, OUTPUT);
  digitalWrite(14, LOW);
  digitalWrite(15, HIGH);
  
  // Инициализация шины I2C
  Wire.begin();
  delay(500);
  mpu.initialize(); // Инициализация акселерометра
  LCD.init(); // инициализация LCD дисплея
  delay(100);
  LCD.backlight(); // включение подсветки дисплея
  State = CALIBRATION;
  
  // Инициализация массива регистров
  *p_angle=0;
  *p_angle_speed=0;
  *p_angle_integral=0;
  *p_position=0;
  *p_position_speed=0;
  *p_position_integral=0;
  *p_control_value=0;
  *p_is_local_mode = true; 
  *p_fix_claim_id=0;
  *p_initional_flag=0;
  *p_duration_time=DEFAULT_DURATION_TIME;
  *p_delta_angle_bias=65; // угол соответствует 0.65 градусам См. holding_decimals[]
  *p_index_pid=1;
  
  
  //slave.poll( holding, HOLDING_SIZE);  
  
  // Настройка портов для работы энкодеров
  pinMode(EncoderPinMSB1, INPUT); //датчик угла 1
  pinMode(EncoderPinLSB1, INPUT); //датчик угла 1
  pinMode(EncoderPinMSB2, INPUT); //датчик угла 2
  pinMode(EncoderPinLSB2, INPUT); //датчик угла 2
  
  digitalWrite(EncoderPinMSB1, HIGH); //turn pullup resistor on
  digitalWrite(EncoderPinLSB1, HIGH); //turn pullup resistor on
  digitalWrite(EncoderPinMSB2, HIGH); //turn pullup resistor on 
  digitalWrite(EncoderPinLSB2, HIGH); //turn pullup resistor on

  // Разрешение прерываний
  attachInterrupt(1, UpdateEncoder1, CHANGE); //EncoderPinLSB1=3 INT.1
  attachInterrupt(0, UpdateEncoder1, CHANGE); //EncoderPinMSB1=2 INT.0
  attachInterrupt(4, UpdateEncoder2, CHANGE); //EncoderPinMSB2=19 INT.4
  attachInterrupt(5, UpdateEncoder2, CHANGE); //EncoderPinLSB2=18 INT.5

  // Настройка портов для управления двигателями
  pinMode(MOTOR_A, OUTPUT);
  pinMode(MOTOR_B, OUTPUT);

  // Вывод текста на дисплей
  LCD.clear();
  LCD.setCursor(0, 0);
  LCD.print("Leveling ...");
  calibration();  // Запуск функции горизонтирования
  SetDiodColor(XXX);
  LCD.clear();
  LCD.setCursor(0, 0);
  LCD.print("Leveling done!");
  
  
  // Ожидание определения наклона объекта и корректировка целевого угла
  boolean isNotDirect=true;
  while(isNotDirect)
  {
    if((EncoderValue2 < -50))
    {
      angle_bias = tmpBias + DEFAULT_BIAS - 3894; // поправка при правой калибровке
      isNotDirect=false;    
    }
    if((EncoderValue2 > 50))
    {  
      angle_bias = tmpBias + DEFAULT_BIAS + 25; // поправка при левой калибровке
      isNotDirect=false;
    }
    //slave.poll(holding, HOLDING_SIZE);
  }
  oldTimeStabilisation = millis();
  
  State = FALLED;
   
}

void loop() 
{
  switch(State){
    case READY: // Режим подготовки к эксперименту - ожидание вертикализации
        
                                       
        SetDisplayMessage(OPTIONS);
               
        // работа системы линенйного приведения
        linear_err_limit=100;
        linear_err=EncoderValue1-linear_bias;
        if (linear_err>linear_err_limit)
        {
          analogWrite(MOTOR_A, 100);
          analogWrite(MOTOR_B, LOW);
        }
        if (linear_err<-linear_err_limit)
        {
          analogWrite(MOTOR_A, LOW);
          analogWrite(MOTOR_B, 100);
        }
        if (linear_err<linear_err_limit && linear_err>-linear_err_limit)
        {
          analogWrite(MOTOR_A, LOW);
          analogWrite(MOTOR_B, LOW);
        }
                      
        // работа системы вертикализации
        if (linear_err<linear_err_limit && linear_err>-linear_err_limit)
        {
          Ang=Ang+dAng;
          if (dAng>0)
          {
            servo_left.write(Ang);
          }
          if (dAng<0)
          {
            servo_right.write(Ang);
          } 
        }       
        
        // проверка факта вертикализации и переход в режим стабилизации
        if((EncoderValue2 >= angle_bias - delta_angle_bias) && (EncoderValue2 <= angle_bias + delta_angle_bias))
        { // Переход в состояние стабилизации
          State = STABILISATION;
                    
          servo_left.write(servo_init_left);
          servo_right.write(servo_init_right);
          
          SetDisplayMessage(MENU);
                  
          start_time = millis();
          duration_time*=1000; // перевод длительности эксперимента в миллисекунды
          SetDiodColor(XXG);
          *p_initional_flag=true;
                            
          // !!! Обнуление внутренних переменных регуляторов
          old_position = 0;
          my_position_integral = 0;
          old_angle = 0;
          my_angle_integral = 0;
                   
          // обнуление значений максимального отклонения объекта от цели
          maxLinear = 0;
          maxAngle = 0;
        }
      
      break;
    
    case STABILISATION:
      // Регулятор времени цикла управления
      do
      {
        periodStabilisation = millis()-oldTimeStabilisation;
      }
      while(periodStabilisation < control_period);
      oldTimeStabilisation = millis(); 
      
      stabilisation();  // Выработка управляющего воздействия
      break;
   
    case FALLED:
      // выбор сервопривода вертикализации
      if(EncoderValue2 > angle_bias)
        {
          Ang=servo_init_right;
          dAng=-1;
     
        }
      if(EncoderValue2 < angle_bias)
        {
          Ang=servo_init_left;
          dAng=1;
        }
      // выключение моторов
      analogWrite(MOTOR_A, LOW);
      analogWrite(MOTOR_B, LOW);
            
      // печать текущих параметров объекта 
      if(((prevEncoderValue1 >= EncoderValue1 + 10) || (prevEncoderValue1 <= EncoderValue1 - 10)) || ((prevEncoderValue2 >= EncoderValue2 + 10) || (prevEncoderValue2 <= EncoderValue2 - 10)))
        { // Параметры углового или линейного положения были изменены
          prevEncoderValue2 = EncoderValue2;
          prevEncoderValue1 = EncoderValue1;
          oldMenuTime = millis();
        }

      if(millis() - oldMenuTime < 1000)
          // Вывод параметров углового или линейного положения
          SetDisplayMessage(OPTIONS);  
      else
         // Вывод меню
        SetDisplayMessage(MENU);
        
      if (is_local_mode==false)
      {
         if (*p_fix_claim_id != 0)
         {
            duration_time=int(*p_duration_time);
            delta_angle_bias=int(*p_delta_angle_bias*22.22/pow(10,*p_delta_angle_bias_decimals));
            index_pid=*p_index_pid;
            SetStateReady();
         }
      }
      else
      {
        
      }
      
      
   break;
  }
  //  Обработка нажатия кнопки
  char key = pad.getKey();  // Проверка нажатия кнопки
  if(key)  
    handlerKey(key);
  slave.poll(holding, HOLDING_SIZE);
}

inline __attribute__((always_inline)) void handlerKey(char key){
// Функция обработки нажатия клавиши клавиатуры
  switch(State){
    case READY:
      switch(key){
          case '2': // Переключение алгоритма
            break;
          case '3': // Вкл/Выкл обмен данными с ОРС сервером
            break;
          case '4': // Выключение СУД
            //while(EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle));
            servo_left.write(servo_init_left);
            servo_right.write(servo_init_right);
            SetDiodColor(XXX);
            State = FALLED;
            break;
      }
      break;
    case STABILISATION:
      switch(key){
          case '1': // Обнуление максимально достигнутых параметров
            maxLinear = 0;
            maxAngle = 0;
            break;
          case '3': // изменение режима управления: local/remote
            if (is_local_mode) is_local_mode=false;
            else is_local_mode=true;
            *p_is_local_mode=is_local_mode;
            SetDisplayMessage(MENU);
            break;
          case '4': // Выключение СУД
            //while(EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle));
            SetDiodColor(XXX);
            State = FALLED;
            break;
      }
      break;
    case FALLED:
      switch(key){
        case '1':
          softReset();
          break;
        case '2': // Переключение набора коэффициентов ПИД регулятора
          if (is_local_mode)
          {
            index_pid+=1;
            index_pid%=N_PIDS;
          }
          break;
        case '3': // изменение режима управления: local/remote
          if (is_local_mode)
          is_local_mode=false;
          else is_local_mode=true;
          *p_is_local_mode=is_local_mode;
          SetDisplayMessage(MENU);
          break;  
        case '4': // Переход в режим подготовки к стабилизации
          if (is_local_mode)
          {
            duration_time=DEFAULT_DURATION_TIME;
            delta_angle_bias=(int) (DEFAULT_DELTA_ANGLE*22.22);
            SetStateReady();
          }
          break;
      }
      break;
  }
  delay(100);
  
}



inline __attribute__((always_inline)) void calibration(){
  int16_t ax, ay, az, gx, gy, gz;
  double tmpAngle = 0;
  
  LCD.setCursor(0, 1); // ставим курсор на 1 символ второй строки
  for(int i = 0; i < COUNT; i++)
  {
    mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz); // Получение параметров ускорений по осям
    tmpAngle += ((double)ay)/COUNT; // Усреднение значения ускорения свободного падения
    if((i % (COUNT/16)) == 0)      
      LCD.write(255); 
  }  
  // Введение поправки в целевой угол
  tmpBias = (((3.1415/2) - acos((tmpAngle - horizontErr)/G))*8000)/(2*3.1415);
  //angle_bias = EncoderValue2 + DEFAULT_BIAS - tmpBias;
  linear_bias = EncoderValue1;
  
}

inline __attribute__((always_inline)) void stabilisation()
// Функция реализующая управляющее воздействие на один период стабилизации 
{
  if((EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle)) && 
    (EncoderValue1 > (linear_bias - criticalLinear) && EncoderValue1 < (linear_bias + criticalLinear)) &&
    millis()-start_time <= duration_time)
  {
    
      // Расчет управляющего воздействия по алгоритму
    linearStabAngle = computePIDlinear(EncoderValue1, linear_bias, kPlinear, kIlinear, kDlinear, control_period);
    control_value = computePIDangle(EncoderValue2, angle_bias - linearStabAngle, kPangle, kIangle, kDangle, control_period); 
    *p_control_value=control_value;
    
        
    // Выдача управляющего ШИМ сигнала
    if(control_value < -MIN_POWER)
    {
      control_value = -control_value;
      if(control_value > 1023)
        control_value = 1023;
      analogWrite(MOTOR_A, (control_value == 255?256:control_value));
      analogWrite(MOTOR_B, LOW);
    }
    else if(control_value > MIN_POWER)
    {
      if(control_value > 1023)
        control_value = 1023;
      analogWrite(MOTOR_B, (control_value == 255?256:control_value));
      analogWrite(MOTOR_A, LOW);
    }
    else
    {
      analogWrite(MOTOR_A, LOW);
      analogWrite(MOTOR_B, LOW);
    }
    // Созранение максимально достигнутых параметров отклонения
    if(abs(EncoderValue2 - angle_bias) > maxAngle)
        maxAngle = abs(EncoderValue2 - angle_bias);
    if(abs(EncoderValue1 - linear_bias) > maxLinear)
        maxLinear = abs(EncoderValue1 - linear_bias);
    if(maxLinear != prevMaxLinear || maxAngle != prevMaxAngle)
    {
        //SetDisplayMessage(MAXVALUES);
        //LCD монитор тормозит цикл управления             
        prevMaxLinear = maxLinear;
        prevMaxAngle = maxAngle;
    }
  }

  
  else
  { // Переход в состояние аварии
    analogWrite(MOTOR_A, LOW);
    analogWrite(MOTOR_B, LOW);
    *p_fix_claim_id=0; // информирование о сбросе заявки
    *p_delta_angle_bias=DEFAULT_DELTA_ANGLE;
    *p_initional_flag=false;
    State = FALLED;
    SetDiodColor(XXX);
  }
}

long computePIDangle(int input, int setpoint, double kp, double ki, double kd, unsigned long dt)
// Функция, реализующая подчиненный регулятор
{
  int my_angle = setpoint - input;
  my_angle_integral += my_angle * dt;
  double my_angle_speed = ((double)(my_angle - old_angle)) / dt;
  old_angle = my_angle;
  *p_angle=my_angle;
  *p_angle_integral=my_angle_integral;
  *p_angle_speed=my_angle_speed;
  return (my_angle * kp + ((double)my_angle_integral)*ki + my_angle_speed * kd);
}


long computePIDlinear(int input, int setpoint, double kp, double ki, double kd, unsigned long dt)
// Функция, реализующая ведущий регулятор
// control_value = computePIDangle(EncoderValue2, angle_bias - linearStabAngle, kPangle, kIangle, kDangle, control_period);
{
  int my_position = setpoint - input;
  my_position_integral += my_position * dt;
  double my_position_speed = ((double)(my_position - old_position)) / dt;
  old_position = my_position;
  *p_position=my_position;
  *p_position_integral=my_position_integral;
  *p_position_speed=my_position_speed;
  return (my_position * kp + ((double)my_position_integral)*ki + my_position_speed * kd);
}


// Обратотка информации с датчика линейного положения
void UpdateEncoder1() 
{ 
 int MSB = digitalRead(EncoderPinMSB1); //MSB = most significant bit 
 int LSB = digitalRead(EncoderPinLSB1); //LSB = least significant bit 
 int encoded = (MSB << 1) | LSB; //converting the 2 pin value to single number 
 int sum = (lastEncoded1 << 2) | encoded; //adding it to the previous encoded value 
 if (sum == 0b1101 || sum == 0b0100 || sum == 0b0010 || sum == 0b1011) EncoderValue1 ++; 
 if (sum == 0b1110 || sum == 0b0111 || sum == 0b0001 || sum == 0b1000) EncoderValue1 --; 
 lastEncoded1 = encoded; //store this value for next time
// AngleValue1 = (double)2 * 3.1415 * EncoderValue1 / 1320; //пересчет показаний в радианы
} 

// Обратотка информации с датчика углового положения
void UpdateEncoder2() 
{ 
 int MSB = digitalRead(EncoderPinMSB2); //MSB = most significant bit 
 int LSB = digitalRead(EncoderPinLSB2); //LSB = least significant bit 
 int encoded = (MSB << 1) | LSB; //converting the 2 pin value to single number 
 int sum = (lastEncoded2 << 2) | encoded; //adding it to the previous encoded value 
 if (sum == 0b1101 || sum == 0b0100 || sum == 0b0010 || sum == 0b1011) EncoderValue2 ++; 
 if (sum == 0b1110 || sum == 0b0111 || sum == 0b0001 || sum == 0b1000) EncoderValue2 --; 
 lastEncoded2 = encoded; //store this value for next time
// AngleValue2 = (double)2 * 3.1415 * EncoderValue2 / 8000; //пересчет показаний в радианы
} 

// отображение на дисплее параметров объекта
void SetDisplayMessage(int message)
{
  switch (message)
  {
    case OPTIONS:
      LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
      LCD.print("Pos: "); // печатаем сообщение на первой строке
      LCD.print((2 * R * 3.1415 * (EncoderValue1 - linear_bias) / 1320)); // печатаем сообщение на первой строке
      LCD.print(" cm    "); // печатаем сообщение на первой строке
      LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
      LCD.print("Ang: "); // печатаем сообщение на первой строке
      LCD.print((double)degrees(2 * 3.1415 * (EncoderValue2 - angle_bias) / 8000)); // печатаем сообщение на первой строке
      LCD.write(223); 
      LCD.print("     "); // печатаем сообщение на первой строке
      break;
    case MENU:
      LCD.setCursor(0, 1); // ставим курсор на 1 символ второй строки
      LCD.print("Mod('3'): "); 
      if(is_local_mode == true)
      {
        LCD.print("local "); // печатаем сообщение на первой строке
        LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
        LCD.print("Alg('2'):       ");
        LCD.setCursor(10, 0);
        LCD.print(index_pid); // печатаем номер заявки на первой строке
      }
      else
      {
        LCD.print("remote "); // печатаем сообщение на первой строке
        LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
        LCD.print("Claim id:       ");
        LCD.setCursor(10, 0);
        LCD.print(*p_fix_claim_id); // печатаем номер заявки на первой строке
      }
      break;
    case MAXVALUES:
       LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
       LCD.print("L");
       LCD.print("|Max(cm):");
       LCD.print((2 * R * 3.1415 * (maxLinear) / 1320)); // печатаем сообщение на первой строке
       LCD.print("  ");
       LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
       LCD.print("M");
       LCD.print("|Max( ");
       LCD.write(223);
       LCD.print("):");
       LCD.print((double)degrees(2 * 3.1415 * (maxAngle) / 8000)); // печатаем сообщение на первой строке
       LCD.print("  "); // печатаем сообщение на первой строке
       break;
  }
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

void SetStateReady()
// подготовка к переходу в состояние READY
{
  State = READY;
  SetDiodColor(RXX);
  // выбор и подготовка коэффициентов ПИД регулятора
  kPangle=pid_value[index_pid][0]/pow(10,pid_decimals[0]);
  kIangle=pid_value[index_pid][1]/pow(10,pid_decimals[1]);
  kDangle=pid_value[index_pid][2]/pow(10,pid_decimals[2]);
  kPlinear=pid_value[index_pid][3]/pow(10,pid_decimals[3]);
  kIlinear=pid_value[index_pid][4]/pow(10,pid_decimals[4]);
  kDlinear=pid_value[index_pid][5]/pow(10,pid_decimals[5]);
}

// Перезагрузка МК
void softReset() {
  asm volatile ("jmp 0");
}
