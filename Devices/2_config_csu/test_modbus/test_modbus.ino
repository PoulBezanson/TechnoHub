#include <ModbusRtu.h>


// Инициализация modbus шины
#define HOLDING_SIZE 11 // Количество каналов для OPC сервера
#define ID 100      // Адрес МК для обмена данными с ОРС сервером

#define DEFAULT_CONTROL_PERIOD 10 // Период цикла управления по умолчанию (мс)
int controlPeriod = DEFAULT_CONTROL_PERIOD; // Переменная указывающая требуемый цикл управления
unsigned long oldTimeStabilisation = 0;
unsigned long periodStabilisation = 0;

Modbus slave(ID, 0, 0);  // Объект для работы с ОРС сервером
uint16_t holding[HOLDING_SIZE]; // modbus регистры
int holding_decimals[HOLDING_SIZE]={0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0};
// указатели на регистры
uint16_t *p_angle=holding;
uint16_t *p_angle_speed=holding+1;
uint16_t *p_position=holding+2;
uint16_t *p_position_speed=holding+3;
uint16_t *p_control_value=holding+4;  
uint16_t *p_is_local_mode=holding+5; 
uint16_t *p_fix_claim_id=holding+6;
uint16_t *p_initional_flag=holding+7;
uint16_t *p_duration_time=holding+8;
uint16_t *p_delta_angle_bias=holding+9;
uint16_t *p_index_pid=holding+10;

// указатели decimals регистров
int *p_delta_angle_bias_decimals=holding_decimals+9;
//

void setup()
{
  slave.begin(9600);
    

  oldTimeStabilisation = millis();
}

void loop() 
{
  // Регулятор времени цикла управления
  //*
  do
  {
    periodStabilisation = millis()-oldTimeStabilisation;
    slave.poll(holding, HOLDING_SIZE);
  }
  while(periodStabilisation < controlPeriod);
  //*/
  oldTimeStabilisation = millis();  
  
  *p_angle=1;
  *p_angle_speed=2;
  *p_position=3;
  *p_position_speed=4;
  *p_control_value=5;
  
  
}

