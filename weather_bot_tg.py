import pyowm
import telebot

from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
from pyowm.commons.exceptions import NotFoundError
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo
from datetime import datetime, timezone as dt_timezone
from collections import Counter

config_dict = get_default_config()
config_dict['language'] = 'ru'
owm = pyowm.OWM('-------', config_dict)
bot = telebot.TeleBot("----", parse_mode = None)

def global_weather(place):
    mgr = owm.weather_manager()
    observation = mgr.weather_at_place(place)
    forecast = mgr.forecast_at_place(place, '3h')
    weather = observation.weather
    return weather, observation, mgr, forecast

def weather_for_location(observation):
    location = observation.location
    lat = location.lat
    lon = location.lon
    status = observation.weather.detailed_status
    return location, lat, lon, status

def temp_now(weather):
    temp_dict_celsius = weather.temperature('celsius')
    temp = temp_dict_celsius['temp']
    feels_like_temp = temp_dict_celsius['feels_like']
    return temp, feels_like_temp

def rain_in_3h(mgr, place):
    rain_dict = mgr.weather_at_place(place).weather.rain
    result_rain = rain_dict.get('3h', 0)
    return result_rain

def forecast_tomorrow(forecast):
    weathers = forecast.forecast.weathers[:8]
    temps = [w.temperature('celsius')['temp'] for w in weathers]
    temp_min = min(temps)
    temp_max = max(temps)
    statuses = [w.detailed_status for w in weathers]
    most_common_status = Counter(statuses).most_common(1)[0][0]
    status_to_adj = {
        'ясно': 'ясная',
        'солнечно': 'солнечная',
        'пасмурно': 'пасмурная',
        'снег': 'снежная',
        'дождь': 'дождливая',
        'небольшой дождь': 'дождливая',
        'гроза': 'грозовая',
        'облачно с прояснениями': 'облачная с прояснениями',
        }
    weather_adj = status_to_adj.get(most_common_status.lower(), most_common_status)
    return weathers, temp_min, temp_max, statuses, weather_adj

def sunrise_and_sunset_time(weather, lat, lon):
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lon)
    local_tz = ZoneInfo(timezone_str)
    sunrise_utc = weather.sunrise_time(timeformat='date')
    sunrise_local = sunrise_utc.astimezone(local_tz)
    sunrset_utc = weather.sunset_time(timeformat='date')
    sunrset_local = sunrset_utc.astimezone(local_tz)
    sunrise_formatted = sunrise_local.strftime('%H:%M')
    sunset_formatted = sunrset_local.strftime('%H:%M')
    daylighttime = sunrset_local - sunrise_local
    hours = daylighttime.seconds // 3600
    minutes = (daylighttime.seconds % 3600) // 60
    return local_tz, sunrise_local, sunrset_local, sunrise_formatted, sunset_formatted, daylighttime, hours, minutes

def visibility_distance(observation):
    visibility_m = observation.weather.visibility_distance
    visibility_km = visibility_m / 1000
    return visibility_km

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Приветствую, я бот который поможет узнать погоду в твоем городе. Итак, погода в каком городе тебя интересует?\n Напиши город в формате: Берлин, Киев, Вашингтон, Новый-Орлеан, Ивано-Франковск.")
    
@bot.message_handler(content_types=['text'])
def user_weather_city(message):
    place = message.text.strip()

    try:
        weather, observation, mgr, forecast = global_weather(place)
    except NotFoundError:
        bot.reply_to(message, "Не удалось найти такой город. Попробуйте ещё раз.")
        return
    except Exception:
        bot.reply_to(message, "Произошла неожиданная ошибка. Попробуйте позже.")
        return
    
    try:
    
        location, lat, lon, result = weather_for_location(observation)
        temp, feels_like_temp = temp_now(weather)
        result_rain = rain_in_3h(mgr, place)
        weathers, temp_min, temp_max, statuses, weather_adj = forecast_tomorrow(forecast)
        local_tz, sunrise_local, sunrset_local, sunrise_formatted, sunset_formatted, daylighttime, hours, minutes = sunrise_and_sunset_time(weather, lat, lon)
        visibility_km = visibility_distance(observation)

        current_utc_time = datetime.now(dt_timezone.utc)
        current_place_time = current_utc_time.astimezone(local_tz)
        current_time_formatted = current_place_time.strftime('%H:%M')

        response = (
            f'В городе {place} сейчас - {result}.\n'
            f'                                        \n'
            f'Местное время - {current_time_formatted}.\n'
            f'                                        \n'
            f'Температура составляет - {round(temp)} градус(ов), ощущается как - {round(feels_like_temp)}.\n'
            f'                                        \n'
            f'Количество осадков за последние 3 часа составляет - {result_rain} мм.\n'
            f'                                        \n'
            f'Дальность видимости сегодня составит - {round(visibility_km)} километров.\n'
            f'                                        \n'
            f'Время рассвета сегодня: {sunrise_formatted}, время заката: {sunset_formatted}.\n'
            f'                                        \n'
            f'Продолжительность светового дня составит {hours} часов, {minutes} минут.\n'
            f'                                        \n'
            f'На завтра погода ожидается {weather_adj}, с температурой от {round(temp_min)} до {round(temp_max)} градусов по цельсию.'
        )

        bot.send_message(message.chat.id, response)

    except Exception as e:
        print(f"[DEBUG] Ошибка в обработке данных: {e}")
        bot.reply_to(message, "При обработке данных что-то пошло не так. Попробуйте снова.")
        return
    
bot.infinity_polling()

