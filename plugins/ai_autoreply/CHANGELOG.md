# Changelog

## 0.9.7
- Новый переключатель чата «Видеть кадр видео и кружков» (нужно «Видеть медиа», приложение 0.2.7+): вместо маленького превью модель получает настоящий кадр присланного видео, кружка или GIF.
- Если собеседник говорит о видео, кружке или гифке, которые присылал раньше («посмотрел видео?»), бот видит кадр последнего такого сообщения.
- Раздел «Доступ ИИ» чата получил страницу «Расширенные настройки общения»: «Видеть медиа», «Видеть кадр видео и кружков», «Распознавать голосовые» в одном месте.
- Био собеседника берётся через открытый вызов приложения 0.2.7+ (старый путь остаётся запасным).
- На старых приложениях (0.2.5, 0.2.6) всё работает как раньше, лишних пунктов не появляется. Отправка гифок и голосовых от вашего имени пока недоступна: в приложении нет нужного вызова.

## 0.9.6
- «Память стиля в Neon» (на странице «Память в Neon» личного чата, по умолчанию выключено, согласие на каждый чат): пары «их сообщение → ваш настоящий ответ», чем закончились предложенные ответы («+», «- свой текст», «неважно» в «Спрашивать меня о важном») и короткие факты о собеседнике хранятся 90 дней на вашем AI-сервере. Перед ответом из Neon подставляются до 3 похожих прошлых ответов и факты, всё внутри общего бюджета памяти 3000 знаков и как цитаты, а не инструкции.
- «Хранить и сами сообщения» отдельным тумблером в том же разделе: по умолчанию выключено, до 200 сообщений на чат, 30 дней. Обычное включение облачной памяти теперь переносит только сводку чата.
- Группы в Neon больше не сохраняются совсем: ни сообщения, ни пары. Кнопка удаления памяти стиля требует второго нажатия.
- Нужны приложение с правом memory.style (0.2.5+); без него раздел стиля показывает подсказку и ничего не отправляет.

## 0.9.5
- На странице «Общение» у личного чата появился пункт «Память этого чата»: шкала заполнения сводки (проценты, знаки из 8000, когда обновлена, заметок из 12) и предупреждение от 90%.
- «Начать память заново»: сводка становится пустой, заметки о собеседнике очищаются, уже сказанное заново не пересказывается. «Вернуть прошлую память» откатывает сводку и заметки. Старые версии сводки остаются на телефоне. Если для чата включена память в Neon, она не трогается; удалить её можно отдельной кнопкой с двойным нажатием.
- Память на один ответ не больше 3000 знаков: сводка и выдержки из Neon делят бюджет (сводка до 1500, когда выдержки есть). У чатов без Neon ничего не меняется.
- Память в Neon теперь ищет выдержки по входящему сообщению, а не берёт просто последние. Если ничего не нашлось, берутся последние, как раньше.

## 0.9.4
- У чата новая страница «Общение»: на неё перенесены «Начать диалог», «Освежить тему сейчас», «Тест стиля в этом чате» и реакции, а также новые пункты ниже. Основная страница чата снова не длиннее 14 пунктов.
- «Как общаться дальше»: временное правило для этого чата, например «больше флирта» или «меньше вопросов». Действует «Правило действует (дней)», по умолчанию 3 дня, потом снимается само. Изменение текста начинает отсчёт заново, в подсказке видно, сколько дней осталось.
- «Изучить чат»: сразу изучает ваш стиль и факты из истории этого чата (до 100 сообщений), прогресс и итог показываются всплывающими сообщениями. Работает и при выключенном «Запоминать факты о собеседниках».
- «Писать ежедневно» (личные чаты в режиме Авто, по умолчанию выключено): раз в день, в случайное время с 9 до 21, не в тихие часы, бот пишет первым, если вы с человеком ещё не общались в этот день. Идёт тем же путём, что оживление разговора, с теми же лимитами (часовые и дневные лимиты, «Оживление: раз на чат в сутки»).
- «Общаться как в другом чате…»: выберите чат того же аккаунта, и ваши сообщения из него станут примерами стиля здесь (недостающие добираются из этого чата). «Стиль этого же чата» возвращает как было.

## 0.9.3
- Исправлена «петля», когда бот переставал отвечать: если он уже ответил много раз за 2 минуты («Ответов за 2 минуты, считающихся петлёй»), следующее сообщение собеседника раньше молча выбрасывалось насовсем, и страховочное сканирование его тоже не подбирало. Теперь сообщение ждёт, пока окно освободится, и бот отвечает на него.
- Все случаи, когда бот решил не отвечать или подождать (лимиты, паузы, пауза в группе, ожидание вашего ответа в «Избранном»), пишутся в лог плагина с причиной. В логе нет текстов сообщений и id чатов: вместо id стоит короткая метка chat#xxxxxx.
- «Стиль → Иногда пропускать запятые»: бот иногда пропускает запятые, как живой человек. Шанс для каждой запятой, по умолчанию 30%. Делается после ИИ, числа вроде 1,5 и ссылки не трогаются.
- «Стиль → Опечатки»: шанс одной опечатки в сообщении (пропущенная, переставленная или удвоенная буква в середине длинного слова, например «магзин»). По умолчанию 0. Правило «без опечаток» для ИИ осталось, опечатки добавляются после.
- «Медиа → Наборы стикеров»: можно перечислить через запятую названия паков, из которых бот берёт стикеры. Пусто = любые. Работает только со стикерами из недавних и избранных, подсказка показывает, какие паки там видно.
- После ошибки на главной странице настроек появляется «Последняя ошибка» (сутки), внутри неё «Отправить отчёт в чат…» и «Скопировать отчёт» (последний час, без текстов и имён) и «Скрыть эту ошибку».
- На странице личного чата кнопка «Начать диалог»: бот сразу пишет приветствие, как команда .ai start.
- Бот видит @username и описание профиля (био) собеседника, если они есть в кэше приложения, и использует их, только когда это к месту.

## 0.9.2
- План общения для личного чата (необязательно): «Чат → Лор и заметки → План общения», одна строка на день общения, например «День 1: знакомство», «День 2: общие интересы». Бот мягко ведёт разговор к теме текущего этапа, но не навязывает её и идёт за собеседником. Следующий этап начинается на следующий день общения или раньше, если собеседник сам заговорил о теме более позднего этапа. Назад этап не возвращается, при изменении плана отсчёт начинается заново. Текущий этап виден в подсказке. Лишних запросов к ИИ нет, правила коротких ответов из 0.9.1 действуют.
- «Спрашивать меня о важном» (Обо мне, по умолчанию выключено): если ответ назначает встречу или время, касается денег, обещания, согласия или отказа от вашего имени, бот не отправляет его сам, а присылает вам в «Избранное» что написал собеседник и что бот хочет ответить. Ответьте на это сообщение «+» (отправить), «- ваш текст» (отправить ваш вариант; просто «-» = ничего не отправлять) или «неважно» (отправить и больше не спрашивать в этом чате о том же, например о суммах в гривнах). Можно и без ответа на сообщение: голое «+», «-» или «неважно» относится к последнему вопросу, «#N …» к вопросу с номером N. Другие ваши заметки в «Избранном», например «- купить молоко», бот не трогает. Пока бот ждёт, он не читает чат, не печатает и не отвечает на новые сообщения; после вашего ответа продолжает с новыми. Если вы не ответили за «Ждать моего ответа» (по умолчанию 30 минут), ничего не отправляется, в «Избранное» приходит короткая заметка. В приложении 0.2.6 и новее вопрос приходит уведомлением, в старых видно только в «Избранном» (и всплывашкой, если приложение открыто). Важность ИИ отмечает в том же запросе, плюс страховка по словам (деньги, «договорились», «приеду», «обещаю»…). Вопрос без ответа теряется при перезапуске приложения, и тогда ничего не отправится.

## 0.9.1
- Ответы короче и живее: длина ответа примерно как у входящего сообщения (на «как ты?» несколько слов, не больше 60 знаков; на длинное сообщение до двух его длин), одно сообщение не длиннее 160 знаков. Если ИИ написал слишком длинно, он один раз переписывает короче, потом лишнее обрезается по концу предложения. При «Подробных» ответах длина не ограничивается.
- В темпе «Живой человек», в «Естественном общении» и при выключенных «Коротких сообщениях» не больше 2 сообщений подряд.
- Без длинных тире и кавычек «» в ответах: тире заменяется запятой.
- Если собеседник раздражён или просит прекратить («хватит уже», «отстань», «досить», «стоп»…), бот коротко признаёт это и бросает тему, ответ не длиннее сообщения собеседника. Слова ищутся целиком: «стопудово», «хватит ли денег», «мне досталось» не считаются.
- Цитаты: если бот отвечает не на последнее из новых сообщений (например, на вопрос, после которого пришло ещё что-то), он цитирует его. Иначе цитирует изредка: «Цитировать сообщение: шанс (%)», по умолчанию 10, в «Длина и разбиение».
- На стикер бот чаще отвечает словами, стикером примерно в 30% случаев (раньше всегда стикером).
- «Печатает…» видно перед каждым ответом не меньше 2 секунд, дольше для длинного текста, обновляется каждые 4 секунды.
- После паузы чата бот, как и раньше, читает последние сообщения перед ответом и не отвечает на то, на что вы уже ответили сами (добавлены тесты).
- Размер больше 512 КБ: версия 0.9.1 нужна приложению 0.2.5 и новее, в старых приложениях остаётся 0.9.0.

## 0.9.0
- Тумблеры «Человеческий темп ответов», «Игнорировать простые ок / спасибо / лол», «Группы: только вопросы и просьбы» и «Страховочное сканирование» теперь показывают то, что реально работает при выбранном темпе. Раньше при темпах «Сбалансированный», «Разговорчивый» и «Тихий» они были включены на экране, а фактически выключены.
- На странице «Сервис» снова есть кнопка «Скопировать отчёт (последний час)».
- Страницы не длиннее 14 пунктов: добавление чата вынесено на отдельную страницу «Добавить чат», в списке чатов до 6 чатов (при одном аккаунте), остальные под «Показать все»; «Задержки подробно» разделены, холодный старт и долгое ожидание на отдельной странице «Холодный старт».
- Пункты меню чата меняют язык сразу после смены «Языка интерфейса», без перезапуска плагина.
- Пункт «Бот в этом чате: выкл.» не показывается в каналах, секретных чатах и ботах, где бот работать не может (по данным из кэша приложения).
- «Ответов в день на чат»: 0 = без лимита, как у часового лимита.
- Тексты: подсказки ссылаются на настоящие названия страниц и переключателей, единые термины («Естественное общение», «сводка» памяти, «Живая беседа» и «Холодный старт»), исправлены «в личке», «о нём», апострофы в украинских строках и др. Подсказки у «Вернуть значения темпа» и «Помечать ИИ в первом ответе».

## 0.8.1
- Оживление разговора можно включить и в группах: переключатель «Оживляти і в групах» (по умолчанию выключен), работает только в чатах в режиме Авто.
- Лимит оживлений на чат в сутки по умолчанию 3 вместо 1 (настройка до 10). Если собеседник не ответил на прошлое оживление, новое не отправляется.

## 0.8.0
- Настройки разложены по страницам: на главной видно, работает ли бот, и категории со строкой текущего состояния (Чаты, Очередь ответов, Обо мне, Манера общения, Стикеры и медиа, Темп и лимиты, Память, Модель и промпт, Команда .ai, Сервис). Числа задержек, разбиение и фильтры ушли на страницы «подробно». В приложении без страниц остаётся прежний экран с «Разделом».
- У каждого человека своя страница: включение, режим, «Освежить тему сейчас», пол и язык, стиль, тон, реакции, промпт, «Лор и заметки» (имя, возраст, город, что ещё знаете о нём) и «Доступ ИИ» (память, фото, голосовые, облако). Тон и поля лора человека новые, по умолчанию «как в общих» и пусто.
- Простой и расширенный вид. Новая установка без чатов начинается с «Быстрой настройки» из трёх шагов и простого вида; у тех, у кого чаты уже есть, видно всё, как раньше.
- Очередь ответов: кто ждёт ответа и через сколько, кнопки «Отправить сейчас» и «Остановить» (как если бы вы ответили сами), «Остановить всё». Открытая страница обновляется сама при изменении очереди.
- Шкалы памяти (резюме чатов, размер базы, обновления за сегодня) и интерес собеседника 0–100 без запросов к ИИ (скорость и длина ответов, вопросы, кто начинает, эмодзи, давность); список чатов можно сортировать по интересу, имени или включённым.
- «Что нового» с переходом к нужной настройке, «Отправить отчёт в чат» (тот же отчёт за час без текстов и имён, частями до 4000 символов), «Изменить несколько сразу» для всех, включённых или чатов одного аккаунта.
- Модель для фона и температура выбираются из списка; свои значения на странице «Свои значения».
- Исправлено: на экране чата были видны сырые ключи cloud_title / cloud_consent вместо текста; поле температуры показывало 0.95, хотя работает 0.85; в подсказке команды не было `.аи`. «Удалить чат» и «Очистить журнал» теперь срабатывают со второго нажатия в течение 5 секунд.
- Тексты короче и единообразнее: «до»/«от» и единица в скобках, у пустых полей темпа «Сейчас 15 (по темпу)», у пресетов указаны задержки.
- Пресет «Живой человек» при пустых полях: не больше 150 ответов в час во всех чатах (было без лимита) и 300 в день на чат (было 400); «оживление» затихшего разговора не чаще раза в день на чат (было 2). Сохранённые значения не меняются.
- Файл плагина уменьшен: убраны комментарии с историей версий и длинные описания функций, неиспользуемые строки.

## 0.7.7
- Длинный ответ больше не обрезается с «…» посреди фразы. Если текст не влезает в лимит, бот отправляет то, что влезает целиком (до конца предложения, иначе до запятой, иначе до целого слова), а остаток уходит следующим сообщением, без многоточий и тире. Слово никогда не рвётся. Если сообщений больше, чем разрешено настройкой «Максимум сообщений», короткие части склеиваются, а лишние целые части отбрасываются; в режиме одного сообщения уходит только первая законченная часть. Это работает при включённых «Человечных ответах»; в режиме обычного ассистента обрезка прежняя.
- Новая настройка «Случайный лимит длины: от»: если указать, лимит каждого ответа выбирается случайно между этим числом и «Макс. длиной ответа». Пусто — всё как раньше.
- Enter больше не ставится посреди предложения («норм вроде⏎только в новых пока тупит» → «норм вроде, только в новых пока тупит»). Это закрыто и для текста модели, и для склейки строк, и для постов в группе. Перенос строки остаётся только между законченными мыслями и только с шансом из новой настройки «Перенос строки между мыслями, %» (по умолчанию 10 %).
- Бот не путает себя и собеседника: в запросе лор теперь подписан «ТЫ (автор)» и «СОБЕСЕДНИК», добавлено правило не переносить чужую биографию и не вспоминать родственников, болезни и события, которых нет в переписке. Если ответ всё же говорит о бабушке, маме, болезни или смерти, которых никто не упоминал, он пишется заново; если и второй вариант такой же, рискованное сообщение не отправляется.
- Смех стал естественнее: не два ответа со смехом подряд и не больше двух из последних четырёх, никакого смеха на грустные новости (умер, болею, проблема, ужас…), капс «АХАХАХ» только если собеседник сам очень смеётся, одинаковое «ахах» каждый раз меняется на другое написание. Лишний смех вырезается, без повторного запроса. Выключается переключателем «Естественный смех».
- На вопросы-«проверки» (столица, сколько будет 17×23, что такое…, напиши код) бот отвечает как человек: коротко, «хз», «не помню», «загугли». Если модель всё же написала справку, ответ сокращается до одной короткой фразы. Правило добавляется в запрос только для таких вопросов, обычные ответы не меняются.
- Ваш промпт больше не теряется в длинном запросе. Если запрос не влезает в лимит, сначала сокращаются служебные блоки и лор, потом стандартные правила, а ваш промпт остаётся целиком. Память чата получает только оставшееся место. В конце запроса, после примеров стиля, добавлено короткое напоминание, что ваши инструкции главнее примеров. В журнале при сокращении видно, что сокращено и размер до/после (без текста сообщений).
- В списке моделей появились best-of, glm-5.3, kimi-k3, DeepSeek-V4-Pro, DeepSeek-V4.1-Flash, DeepSeek-V4-Flash и glm-5.3-flash. Для новой установки по умолчанию выбирается best-of; у тех, кто уже пользовался плагином, модель не меняется.
- Если в вашем промпте есть жёсткие правила («никогда», «нельзя», «обязательно», never, must…), температура не поднимается выше 0.8, в том числе при повторной попытке. По умолчанию по-прежнему 0.85.
- Сохранённые настройки не меняются; новые настройки по умолчанию безопасные.

## 0.7.6
- Ответ с «сломанным» словом (например «дависьй») считается браком и пишется заново, как ответ с мусором. Проверяются только сочетания букв, которых нет в русском и украинском («ьй», «ьь», «ъь»), поэтому обычные слова и сленг не страдают.

## 0.7.5
- Бот больше не замолкает на 30 минут из-за медленного ИИ-сервера. Раньше несколько подряд тайм-аутов выключали чат как «сломанный». Теперь тайм-ауты, лимиты и перезапуск сервера считаются временными: сообщение повторяется, чат остаётся включённым. Чат выключается только если сервер не настроен или отклонил токен.
- Если вторая попытка ответа не удалась, отправляется готовый ответ первой, а не теряется всё.
- В журнале теперь видна причина и время: «запрос к ИИ не удался через N с: нет ответа вовремя» вместо «ИИ-сервер не ответил или не настроен».

## 0.7.4
- Иногда в конце ответа появлялся мусор вроде `То "" not possible in tool`: модель выдавала обрывок служебного текста. Теперь такой хвост отрезается, а ответ с мусором перегенерируется при пониженной температуре. Если и вторая попытка с мусором, отправляется последнее законченное предложение.
- Температура по умолчанию снижена с 0.95 до 0.85 (сохранённые значения не меняются): высокая температура на glm-5.3 чаще давала такие обрывки.

## 0.7.3
- Ответы снова пишутся вашим голосом, как в 0.5.x. С 0.7.1 инструкция начиналась со слов «ты автоматический помощник», и ответы звучали как у помощника. На прямой вопрос «это бот?» он по-прежнему честно отвечает.
- Ваши настоящие сообщения и описание вашей манеры теперь идут в самом конце, прямо перед правилом языка.
- Если запрос не помещается в лимит, сначала сокращаются лор и правила, а не примеры: остаётся минимум 12 ваших сообщений. Раньше при длинном лоре и своём промпте примеры пропадали все.
- Размер запроса не вырос, сохранённые настройки не меняются.

## 0.7.2
- Облачная память больше не получает пароли, коды из SMS (цифрами и словами), номера карт, IBAN, CVV и ключи: они заменяются на «(hidden)», а остальной текст сообщения сохраняется, поэтому в памяти не остаётся вопросов без ответа. Телефоны, даты, суммы и номера заказов не трогаются. Итог чата при переносе в облако очищается так же.
- Команда `.ai` перед отправкой заново проверяет, что чат и автоответчик ещё включены, настройки и аккаунт не менялись. Если пока шла генерация что-то изменилось, ничего не отправляется.
- Если облако было занято, собранные сообщения больше не теряются: они ждут и отправляются повторно.
- Перенос локального итога в облако теперь работает только при включённой памяти этого чата.
- Собеседник больше не может подделать служебную строку «личная инструкция от меня» в своём сообщении: квадратные скобки в его тексте заменяются круглыми во всех запросах к AI (ответ, `.ai`, группы, заметки, итог памяти, выбор стикера).

## 0.7.1
- Добавлены стили общения: обычный, тёплый, по делу и сдержанный. Можно выбрать общий стиль или отдельный для чата. Убраны обязательные шутки и лишние заготовленные фразы; короткие реплики и ответы в группе учитывают текущий разговор.
- Обычные слова вроде «розумію» и «конечно» больше не вырезаются и не вызывают повторный запрос. Ваши собственные запреты сохраняются.
- Лимит числа сообщений теперь работает и в естественном режиме. Выключенное разбиение больше не оставляет случайный второй способ разделить ответ.
- Новые значения по умолчанию: до двух сообщений, более короткие ответы и без случайного ожидания на одну-две минуты. Ваши сохранённые значения сохраняются; время генерации учитывается в ожидании.

## 0.7.0
- Отдельная память в Neon для выбранного аккаунта и чата/темы. Нужен ZephyrGram0.2.2 с разрешением ai.memory; по умолчанию всё выключено.
- При включении можно перенести последний сохранённый итог личного чата с телефона. Исходная локальная память сохраняется; группы без авторов/тем не переносятся.
- Сохраняет только новые разрешённые тексты после включения, без полного архива и вложений. История разных людей и тем не объединяется.
- Можно остановить сбор и чтение либо удалить облачную память. Удаление подтверждает сервер; без сети оно остаётся ожидающим и повторяется для того же владельца.
- Смена аккаунта, адреса сервера или ключа не переносит согласие на другой источник. Ошибки памяти не останавливают ответы и не вызывают платных повторов AI.

## 0.6.4
- Если вы ответили сами или выключили автоответчик, ожидание и индикатор «печатает…» теперь тоже останавливаются. Проверка идёт не реже одного раза в 4 секунды; старый ответ не ждёт оставшуюся длинную паузу.
- Исправление работает и с ручным пределом задержки, и в режиме естественных пауз.

## 0.6.3
- В группах ответ приходит одним сообщением, с паузой минимум 20 секунд между ответами. Короткие реплики собираются не менее 6 секунд. Дополнительного стикера после текста в группе нет.
- Разные известные темы обрабатываются по очереди. Если приложение не передало тему, из серии учитывается только последняя реплика, без смешивания разных разговоров; предыдущие реплики пропускаются.
- Латинский ник, ссылка или случайное слово больше не переключают ответ на английский. Явный выбор языка сохраняется.

## 0.6.2
- В группах автоответчик различает, кто что написал и кому ответили. Одинаковые имена больше не считаются одним человеком.
- Разговоры из разных тем не объединяются. Если приложение не передало тему, бот учитывает только одно текущее сообщение, а не всю историю группы.
- Старую общую память и автозаметки групп пока приостановили: они не различали участников и темы. Личная переписка продолжает работать как раньше.

## 0.6.1
- В обычной переписке автоответчик больше не представляет себя нейросетью без вопроса.
- В естественном режиме подпись в первом ответе теперь включается отдельно, по желанию.
- На прямой вопрос, кто отвечает, он по-прежнему отвечает честно.

## 0.6.0
- Явный аккаунт для команд и служебных ответов. Команды, черновики, чтение профиля и ответ при лимите используют выбранный аккаунт. Удаление очищает только его параметры.
- Отмена устаревшей текстовой автоответки. Ручной текст во время генерации/отправки отменяет последующие части; пауза и повторное включение не оживляют старый запрос.
- Восстановление потерянного таймера. Safety-net scan заново запускает ожидающую очередь без таймера, не добавляя то же входящее повторно.
- Обработка границ предложения при лимите. Если целое предложение помещается, ответ заканчивается на его границе. Если границы нет, жёсткое ограничение отмечается многоточием вместо скрытого обрыва.
- Даты в контексте ответа. Передаются текущие UTC-дата/время и датированные выдержки последних сообщений с правилом не выдавать старую новость за сегодняшнюю.
- Ожидание длительности голосового. Добавлен переключатель ожидания длительности голосового, отсчитанного от получения; время генерации уже учитывается. Транскрипция помечается как текстовая расшифровка.
- Off и pause сохраняют настройки. Команды off/pause выключают ответы с сохранением записи, delete удаляет её. Незавершённые старые запросы отменяются.
- Русские команды вместе с английскими. Добавлены .аи офф, .аи пауза и .аи удалить. Существующие стандартные триггеры получают русские варианты; явный нестандартный триггер сохраняет свою область.
- Структурированный лор и локальная замена. В разделе промптов появились необязательные имя, возраст и город; для чата можно дополнять глобальный лор либо использовать только локальный.
- Выбор основной модели списком. В разделе промптов добавлен список: модель приложения/прокси, glm-5.3, DeepSeek-V4.1-Flash. Свой model ID можно сохранить в текстовом поле.
- Реестр отдельных отчётов и ограничений: docs/release-reports.json. Проверка на реальном телефоне ещё не выполнена.

## 0.5.2 (cost control, one model per task, better memory)
- **One request can never balloon.** New "Max size of one AI request" (Limits, `prompt_max`, empty = 24000 characters, about 8k tokens; 8000-60000, nothing can go above 60000). Everything sent with one reply counts: rules, your prompt, style examples, lore and notes, chat memory and history. When it does not fit, pieces shrink in a fixed order: the system part takes at most 55 % (fewer style examples first, then shorter lore, then a hard cut), then the messages being answered get their room, then the chat memory, then the newest history, and the oldest history goes first. Your own prompt (default or per chat) is capped at 4000 characters per request. A typical reply stays as before (about 9-11k characters); the old worst case (context 48000 + lore + memory + an unlimited prompt, 70k+ characters, twice with the retry) is gone. `.ai`, revivals and the style test are bounded the same way.
- **Smart model for replies, cheap model for background work.** New "Cheap model for background work" (Prompts and model, `model_cheap`; empty = the Model above). Used for chat memory summaries, learned chat notes and the sticker picker (which used to call the app default model). Replies, `.ai`, revivals and the style test keep using Model. If the cheap model fails, that task is redone once with the main model and the cheap one is skipped for 30 minutes, so background work never costs more than before 0.5.2.
- **Daily limits for background calls.** "Background AI calls per day" (Limits, `helper_daily`, empty = 200, 0 = none) for all chats together and "Memory updates per chat and day" (Media and memory, `memory_daily`, empty = 6). When a limit is reached the bot keeps answering; memory keeps its last summary, the sticker picker falls back to emoji matching. One summarizer call is bounded too (16000 characters of new messages + the previous summary, at most 30000 per helper request).
- **Chat memory remembers more without bigger prompts.** The summary is now updated incrementally by the cheap model: after 20 new messages (or 4 when the summary is older than 6 hours), at most every 2 minutes per chat, and checked in the background also when the bot does not answer (after 40 messages you or they wrote). A backlog that does not fit one call is chained (up to 3 calls). The app only gives the newest 100 messages; when some were missed the summarizer is told so ("gap") and the log says so. Summaries may be up to 8000 characters (was 6000), the most important facts first; a reply gets only the first 3000. History the summary already covers is no longer sent raw again (except the newest 16 messages), so memory replaces old messages instead of adding to them. Memory storage limit raised to 48 MiB (rows are still never deleted).
- **Memory is on by default in private chats** (new "Chat memory in private chats", Media and memory, `memory_auto`, on). Replies already send the last 40 messages of the chat to the same AI server; the summary only keeps a short digest of them on this phone. With the default, the first summary reads only that reply window, never deeper history; switching memory on in a chat yourself still allows older text. The chat's own memory switch keeps working and wins (a stored "off" stays off); group chats need their own switch. No stored value was changed.
- **See where the tokens go.** The Limits section shows today's reply requests and background calls with token estimates (1 token ~ 3 characters). The report (`.ai log`, "Copy report") has the models and limits, today's and yesterday's requests per kind (count, ~tokens, largest), requests per kind in the last hour, and every AI request in the chat timelines with its size ("AI reply 9120 ch ~3.0k tok"). New log lines: memory updated / gap / daily limit / storage full, background limit reached, cheap model failed, request trimmed.

## 0.5.1
- **If you answered first, the bot takes your message into account.** Before, one message of yours in the middle of a batch silenced the whole batch, even their newer messages that came after yours. Now the messages up to your reply count as answered by you, and the bot answers only what came after it; your own message stays in the conversation the model sees, with a rule not to repeat or contradict it. If you answered everything, the bot still stays silent. The log shows "you answered part of it yourself" for the partial case.

## 0.5.0 (sections, reactions)
- **The settings screen is split into sections.** The first row is a "Section" selector: Main, Chats, Style, Timing and pauses, Limits, Commands, Media and memory, Prompts and model, Style test, Log. Only the chosen section is shown, nothing inside it is folded, so there is no long scrolling any more. Main is short (on/off, answer everyone, accounts, links, short messages, about me, notes, revive, reply language, preset, reactions, interface language); the tone moved to Style. Chats holds the chat list (by account, "show all" over 15, a tap opens a chat's options) and "Add chat"; the decision log is the last section with its buttons. The chosen section is remembered (`ui_section`); no other setting changed its key, type or default.
- **Reactions** (Main -> "Reactions", off by default). "Instead of replying": on "ok / thanks / lol", emoji-only messages and stickers the bot puts an emoji reaction instead of writing (after a human pause in Live, after the read mark) and writes nothing. "Also sometimes on regular ones": additionally, with about 15 % chance, a reaction on a message it has just answered (not on links, at most one per chat in 30 minutes). The emoji is chosen by simple rules without the AI: an emoji message is mirrored when it is in 👍 ❤ 🔥 😁 🥰 👏 🙏 😢 🤔, thanks -> ❤, laughter -> 😁, sadness -> 😢, otherwise 👍. Private chats in mode Auto only; at most 12 per chat and hour and 60 per day; skipped in ghost mode with "do not read". Per chat: "Reactions" in the chat's options (as in general / off / on). Every reaction or skipped reaction is in the log; a failed reaction never breaks the reply or pauses the chat.

## 0.4.9
- **The bot keeps answering while the phone sleeps (needs app 0.2.0 or newer).** The app's background service keeps the process alive, but with the screen off the CPU suspends and the plugin's timers and sleeps (debounce of a few seconds, the human-pace pause, typing waits) stand still until something wakes the phone, for example the owner opening the app; that looked like "the bot does nothing until I come in". The plugin now asks the app to keep the CPU awake (`client.keep_awake`, at most 3 minutes per request, a longer hold is never cut by a shorter one) while it has real work: a message is waiting for its debounce, the AI writes the answer (150 s), the answer is being typed and sent in parts, a revival is being written. The idle safety-net scan never holds the CPU. Older apps without `keep_awake` work as before.

## 0.4.8
- **Gender: it now actually works without setting anything.** Detection no longer needs two self-references from the other person: it also reads how YOU addressed them in the chat history (ти була / ты сделала, красуня, or ти був / братан) and the real history, not only the part that fits into the prompt. Two or more hits = a firm rule; one hit with nothing against it = a hedged rule ("earlier messages suggest ..."). The bot's own earlier lines are never used as evidence.
- **No more masculine by default.** When nothing is known about the other person, the prompt now says so and tells the bot to avoid gender-marked forms (ти зробив/зробила, ты был/была, рад/рада) and rephrase neutrally instead of assuming a man; it also tells the bot not to copy wrong forms from earlier messages. A firm rule overrides earlier wrong forms in the chat.
- **`.ai gender woman | man | auto`** (also `.ai стать жінка`, `.ai пол мужчина`, `.ai gender f|m`): typed in the chat (not sent), sets the other person's gender for this chat.
- **Clearer settings names.** "My own gender (for "I" forms)" in the style group is about the OWNER; the other person's gender is "Her/his gender (for "you" forms)" in the chat's options, and the hint under the first one says where it is.
- **Not the same number of lines every time.** New switch "Vary the number of messages" (on, short-messages mode): neighbouring lines are randomly joined, so an answer goes out as 1 message (40 %), 2 (38 %), 3 (16 %) or more, like a real person, instead of always one line per sentence.

## 0.4.7
- **No more big messages in a row without pauses.** Without a timing preset (Balanced, Chatty, Quiet or Live with human timing off) the typing pause was one shared budget of 2.5 s for the whole answer, so three long parts went out almost at once. Now every part takes as long as a person needs to type it (35 ms per character, jitter, 0.8-20 s per part) with "typing..." refreshed while waiting. Setting "Typing pause cap" by hand still gives the old behaviour (one total budget), and the "Typing pause" switch still turns pauses off.
- **Big single messages are rewritten.** In short-messages mode an answer containing one message longer than 200 characters is rejected once and rewritten with "every message under about 120 characters, one idea per line".

## 0.4.6
- **Forms of address follow the other person's gender.** The bot used to address everybody in masculine forms. Now every answer, `.ai` command and revival gets a gender line: from the OTHER person's own words (needs at least two self-references like "я була / я зробила" or "я був / я зробив", ahead of the other gender by two; Ukrainian and Russian), otherwise a Cyrillic first name ending in а/я as a weak, hedged hint (known male names such as Микита, Ілля, Данила are excluded), otherwise nothing. Per chat you can set it by hand: "Who is this person" (Auto / Man / Woman) in the chat's options; it wins over detection. New global "I am" (Auto / Man / Woman) in the style group tells the bot which forms to use when it speaks about the owner.
- **Pauses follow the length of what is written (human timing).** Every part of a multi-message answer now takes as long as a person needs to type it (`type_ms`, default 35 ms per character, jitter, at most 20 s per part) before it is sent, with "typing..." refreshed while waiting; a long message goes out later than a short one. The first wait counts only the first part (it used to count the whole answer). Short parts keep the usual 1-3 s gap.

## 0.4.5 (sync fixes)
- **The app's Auto-reply tab and the plugin's settings stay in sync.** (1) A change made on the tab while the plugin was writing the chat list (a reply finished, an error counted, "answer everyone" added a chat) could be overwritten, and the other way round: both sides now write under one lock / compare-and-set (needs the matching app update; older apps behave as before). (2) A chat you paused (tab, settings switch) while a request for it was failing, or a chat you switched off after an error pause, no longer turns itself back on 30 minutes later: only a running chat is paused by errors, and your own on/off ends the error pause. The auto-resume checks the stored list, not an older copy. (3) The chat's "Enabled" switch in the settings follows error pauses and auto-resume (`keep_<sk>` is written wherever `enabled` changes); drawing the settings screen no longer writes anything (missing titles are filled on load and after a change on the tab). (4) Changing one chat on the tab (mode, on/off, adding a chat) no longer cancels the reply being prepared in every other chat; only that chat's reply is re-checked. (5) `.ai off` / the menu's off work for a chat that was just added on the tab. (6) Mode changes made on the tab or with the settings selector are now in the decision log ("AI auto-reply screen: mode Friend", "settings: mode Friend"), so it is visible who changed a chat's mode.

## 0.4.4 (diagnostic report)
- **Diagnostic report for the developer.** "Recent decisions" has a new button **Copy report (last hour)**, and the in-chat command **`.ai log`** (also `.ai лог`, `.ai журнал`, `.ai report`, `.ai звіт`, `.ai отчет`; never sent) does the same: in the background the plugin collects one text (at most 15 000 characters) and copies it. It holds the plugin version, time, preset and effective key settings, a summary of the hour (decisions by outcome and reason, incoming -> reply times, suspicious pauses where a message got no reply and no decision for 10+ minutes), and for up to 12 chats the current state (pending, timer, in-flight, cooldown, retries, ...) with warnings for stuck flags, waiting messages without a timer and chats switched off after errors, plus a timeline of decisions and the last 15 messages as time / direction / length / type only. **No message texts, names or usernames** are included; chats appear only as `account:dialog_id`.
- The decision log keeps the last **400** entries (was 60) and is written to the settings at most every 5 seconds (and when the plugin unloads, on copy, clear and report) instead of on every decision. The settings screen still shows the 10 newest entries and "Copy log" still copies the last 40; the stored format is unchanged.
- **The chat memory no longer delays answers.** With "memory" switched on for a chat, every answer first made a separate AI request to compress the old history (timeout 45 s) and waited for it; when it failed the owner saw "compact memory unavailable" and the answer came minutes late. Now the answer uses the summary that already exists and the refresh runs in the background (one at a time per chat). The "memory unavailable" log line is written at most once per half hour per chat.
- **Slow AI is visible in the log**: an answer that took 10 s or more to write adds the entry "the AI needed N s to write the answer".


## 0.4.3
- **`.ai start`** (also `.ai старт`, `.ai welcome`, `.ai привітання`, `.ai приветствие`): typed in a private chat (not sent), it adds the chat to the bot's list (mode Auto, or the mode the chat already has) and the bot writes the first message right away: a greeting when the chat is empty, a natural continuation of the conversation when you already talked. Refused in groups, channels, bots and secret chats.
- **The bot no longer copies messages.** When it is switched on in a conversation that is already going, it used to repeat your last message or hers. Now every answer, `.ai` command and revival is checked against the last 12 messages of the chat: a reply that repeats (or nearly repeats, 90 %+) one of them is rejected once and rewritten with a "do not repeat or paraphrase earlier messages" rule; if it still copies, nothing is sent. Replies shorter than 10 characters are never treated as copies.

## 0.4.2
- **No more 'read but never answered'.** The chat used to be marked as read right after the debounce and the bot could then stay silent (you answered yourself while it waited, the AI failed, an error). Now the read mark is sent only when the answer is ready, right before it is typed.
- **A message is no longer lost to a passing failure.** When the AI request fails, returns nothing, or the chat info/history cannot be loaded, the messages are kept and answered a little later (up to 2 retries, 25 s and 50 s later, logged as "retry ..."). After that the batch is dropped as before and the next message is handled normally.
- **Lore** (new): the setting "Lore: about me" is a free text where you describe yourself for chatting (who you are, what you do and like, how you talk, what is private). Every chat also has "Lore of this chat" (what you know about this person). The AI may state the facts from the lore and nothing else about you; it is told to use them only when relevant, never to recite or contradict them. It is facts, not instructions, and is applied to answers, `.ai` commands and revivals, with or without the humanize mode.
- **Learn notes from chats** (new, off by default, `lore_learn`): after every 25 incoming messages (at most every 10 minutes per chat) the AI reads the recent messages in the background and keeps up to 12 short notes about the person in "Notes learned from this chat", which you can see and edit in the chat's options. Passwords, codes, card/bank data, numbers, links and @usernames are filtered out; the notes are marked as untrusted background in the prompt. Removing a chat deletes its lore and notes.
- New storage keys: `lore`, `lore_learn`, `lore_<sk>`, `learned_<sk>`.

## 0.4.1 (settings screen)
- The settings screen is reorganized for a narrow phone screen. On top, **Main**: master switch, answer everyone (+ accounts), do not answer links, short messages, revive quiet conversations, reply language, tone, preset, interface language. A new user also sees one line on how to start.
- Then the chat list (per account as before) and **Add chat**. With more than 15 chats only the first 15 are shown plus **Show all chats (N)**; an opened chat stays visible. The modes (Auto / Draft / Friend) are explained once, under the chat's Mode selector.
- Everything else is under **More settings** in collapsible groups (tap ▸ / ▾): Style and humanity, Timing and pauses (Live), Limits and protection, Command .ai, Stickers and media, Prompts and model, Style test, Recent decisions (last; shows the 10 newest entries, "Copy log" still copies the last 40). Which group is open is kept in memory only, not in the settings.
- Number fields whose empty value means "use the preset" now show the current preset's value ("Empty = 15"); preset switches show the preset's on/off. Explanations are shortened.
- No setting was removed or renamed: keys, types, defaults and meaning are unchanged, so saved settings keep working.

## 0.4.0
- **Answer everyone** (`reply_all`, off by default): a private chat that is not in the list is added automatically (mode Auto) as soon as its person writes. Bots, groups, channels, secret chats and Telegram service chats are never added; a chat you paused or removed stays as you left it (removals are remembered in `all_skip`, also when removed from the app's chats screen). `all_accounts` limits it to some accounts (1-based numbers).
- **Messages with links are not answered** (`skip_links`, on by default, every chat). Logged as "link".
- **Short messages instead of one long sentence** (`short_msgs`, on by default): the prompt asks for 1-4 short separate lines of simple sentences, each line goes out as its own message (up to `max_parts`, default 4) with the usual typing pauses; a reply made of one run-on sentence (more than 20 words) is rejected once and rewritten. Even a one-line answer longer than 45 characters is split at sentence ends.
- **Quiet conversation revival** (`revive`, off by default): in an Auto chat where a real exchange happened and the other person has not answered for `revive_after` minutes (default 20), the bot restarts the conversation with a topic that fits it (or a natural new one). Only within `revive_window` hours (default 3) of the last message, at most once per silence (not again until they answered), at most `revive_daily` (default 2) per chat and day, never while you are active in the chat, never in quiet hours. Works through the periodic scan; a few chats are examined per pass.
- **The chat no longer stops**: (1) the same text three times in a row is a loop only when the bot has also answered at least three times in the last two minutes, so a person who repeats a word is still answered; (2) when the other person writes while the bot is still sending the parts of its previous answer, the new message is no longer discarded as "the last message is not from them" (the bot's own parts are ordered before it). A message you typed yourself after theirs still keeps the bot silent.
- The settings screen groups chats per account ("Account N - on: x of y") when more than one account is used.
- Review fixes: a revival that fires while a normal reply is running no longer clears that reply's busy flag (which could let two replies run in parallel); a sticker/photo/voice answer counts as an answer for the revival check; the disclosure prefix sent with a revival is remembered. Answer everyone: a failing or empty chat lookup no longer raises or blocks the chat for 10 minutes, service messages ("joined Telegram", calls) and old catch-up messages do not add a chat, and a long removal list keeps the newest removals (it used to drop arbitrary ones). Lines merged to fit `max_parts` keep their line break ("не" + "завтра" no longer becomes "не завтра", and no needless "long sentence" retry); `max_parts` = 1 is no longer split in two by the Live timing.

## 0.3.9
- Added per-chat opt-in local SQLite memory: compact summaries of older text, separated by Telegram owner/account/chat, with bounded storage and cancellation checks. Full histories, audio and images are not copied into the memory database. Recent questions stay in ordinary context; old summaries are untrusted background, not instructions.
- A sticker-only incoming batch in an enabled auto-reply chat uses a dedicated sticker-only response route. No random sticker percentage or AI-decline gate applies. It chooses a recent sticker or queues the incoming sticker through the native outbox, with no text fallback. Explicit draft/command-only modes, disabled chats, cancellation and loop/rate guards still apply.
- Recent conversation context defaults to 40 messages and can be increased to 100, within the app's local-history API limit. A configurable character budget defaults to 16000 (range 2000-48000). Current questions are reserved first, then recent history; oversized content is explicitly marked as trimmed. Messages from other chats/accounts, service messages and secret-chat rows are excluded.
- Current multi-part message batches are merged chronologically with cached history without changing who said what. A message already answered by the owner is not moved to the end as a new question. Existing explicit context sizes remain unchanged.
- Added Short / Balanced / Detailed answer settings. Balanced is the default and allows enough explanation to answer the actual question and every relevant part. The forced 3-12-word/two-sentence/no-explanation instruction is removed. With an empty maximum-length field, the modes allow 400 / 1200 / 3000 characters; an existing explicit limit remains effective (clear a saved 300 limit to use the new mode default).
- Style examples are explicitly labelled as tone/rhythm guidance, never factual memory about the current chat. Borrowing examples from other enabled chats is now off by default and requires a separate opt-in; even with consent it never reads another Telegram account. Up to 100 local style samples can be used, while the prompt includes at most 24 bounded examples.

## 0.3.8
- Added separate per-chat opt-ins for incoming images/stickers/GIF frames and voice transcription. Both default to off. The former global See media setting does not grant permission in any chat.
- Only incoming attachment IDs from the current enabled chat and current batch are fetched, using its explicit Telegram account. At most two bounded images are attached to the reply model. Voice audio uses the configured AI server's transcription endpoint; unsupported/403 failures produce a decision-log entry, no fabricated transcript, and do not disable the chat.
- Media retrieval, transcription, model retries and delivery check the current chat/account and a configuration epoch. Disabling/removing a chat, changing settings or unloading invalidates in-flight attachment work; a late result cannot be sent after cancellation. Text sends/drafts use the explicit account, with safe compatibility fallback only when that account is selected.
- No claim that the current gateway supports speech recognition: its transcription route currently returns 403 and requires separate server configuration.

## 0.3.7
- Stickers are now chosen by CONTEXT, not at random. 'Sticker chance' (default 12 %) is the chance per reply to ask a short AI 'picker' call. The picker sees the last chat messages, the incoming message, the finished text reply and a numbered list of up to 25 of your recent stickers ('3: emoji (set name)') and answers strict JSON {"use_sticker", "index", "reason_emoji", "mode": "instead"|"after"}. It is told to use a sticker only when one naturally fits (laughter, thanks, surprise, sympathy, greeting, agreement/refusal), to answer use_sticker=false when none fits (no sticker beats a wrong one) and never to use one for serious, conflict, informational messages or questions. 'instead' is honoured only for tiny replies.
- Robust parsing: JSON is extracted from surrounding text; on garbage or an AI error the fallback is a sticker whose emoji equals an emoji of the reply, otherwise no sticker. The same sticker or the same sticker set is never used twice in a row in a chat (and the last 6 sticker ids are avoided). Never in groups and never for questions.
- 'See media' (off by default): when the app provides `client.get_message_media`, the picker gets a short description (kind, emoji, set title) of the newest incoming sticker/photo/GIF. Without the call or with the switch off nothing changes.
- Decision log: sticker_decided_yes (with the emoji), sticker_decided_no, sticker_skipped_<no_candidates|repeat|no_match|ai_error|bad_index> (uk/ru/en). A decision record may now carry an optional short field `x` (the emoji).

## 0.3.6
- New preset 'Live (human-like)' is now the DEFAULT for new installs and for settings with no explicit preset (an explicit Balanced/Chatty/Quiet choice stays; those presets are unchanged). Live: burst collected for 2-5 s, 0-3 s between conversational turns, no global hourly cap and 60 replies per hour per chat, loop guard at 10 replies in 2 minutes, plain acknowledgements ('ок', 'дякую') answered about 25 % of the time with a very short line, questions always answered, emoji-only still skipped. A reply is never dropped for being merely similar to the previous one, only for an exact repeat.
- Monitoring: besides the event hooks there is a cheap safety-net scan every ~25 s (60 s when there are no active chats or the master switch is off) that reads the last 8 messages of each enabled chat and feeds incoming messages that no event delivered into the same pipeline, with the same de-duplication and a per-chat last-handled id (survives restarts). It never answers messages older than 'catch-up window' (default 30 minutes), leaves messages younger than 6 s to the events, and also runs once right after app START/RESUME. The scan only schedules timers and worker jobs; it never sleeps and never touches the UI thread.
- The owner's silence rule is 15 s after your last message in the chat and the reply is DEFERRED (up to 8 retries), not dropped. If you answered the message yourself, the bot stays silent ('owner_replied').
- Human timing: the reply latency depends on the situation. Warm talk (their previous message younger than 2 minutes and a recent reply): 2-9 s. Cold start (more than 10 minutes of silence): 8-40 s, 10 % of the time 60-120 s. Slightly longer for long incoming messages and long replies (35 ms per reply character; the warm total is hard-capped at 25 s). While waiting the plugin sends the 'typing...' action (refreshed every ~4 s, cancelled if the reply is abandoned; switch 'Show typing', on by default). 15 % of replies that have a natural break go out as two messages 1-3 s apart. Waiting is done in short sleeps in a worker thread and re-checks the chat and your own activity every 4 s. No night-time behaviour unless quiet hours are set.
- Read marks: the bot marks the chat as read before replying (right after the debounce in a warm talk, right before the typing starts in a cold one). Switch 'Mark messages as read' (on) and 'Read even when the bot does not reply' (off). Private chats only. If ghost mode blocks reading, the decision log says 'read_blocked_by_ghost' (turn off 'do not read' in ghost mode).
- Stickers: with a 12 % chance per reply (setting), only after short emotional/acknowledgement messages and never for questions or in groups, the bot sends a random sticker from your recent ones (first 20, no repeats in a row, matching emoji when possible), after the text or instead of a tiny reply. Needs `client.get_recent_stickers` / `client.send_sticker` (silently off on older apps).
- Reply language: the DEFAULT is now 'The other person's language' - the language of the message being answered (Russian letters/words give Russian, Ukrainian ones Ukrainian; for short messages the last 2-3 incoming ones, then your own messages, then Ukrainian). The prompt states it explicitly. 'Auto (by the owner's context)' is still available; an explicit choice of yours stays.
- Decision log: new reasons scan_found, deferred_owner_active, owner_replied, latency_wait_<seconds>, typing_sent, read_sent, read_blocked_by_ghost, sticker_sent (uk/ru/en). The log keeps 60 entries and shows 40.
- Advanced settings (empty = preset): warm/cold latency ranges and thresholds, long-wait chance, typing speed, warm cap, split chance and pause, acknowledgement chance, loop guard, owner-defer count, cooldown jitter, catch-up window, scan interval, hourly/daily caps (hourly 0 = none).
- Permissions: added `network.requests` (typing and read marks are Telegram requests built with `java.jclass`, since `zephyr.client` has no helper yet; helpers named `set_typing` / `mark_read` are used first when an app provides them, and everything is a silent no-op when neither exists).
- Documented in docs/API.md section 11 and section 10. No storage format change (new optional keys only, including `scan_marks`).

## 0.3.5
- The app's new chats screen (app 0.1.4) edits this plugin's settings and then sends the app event 'settings_changed'. `on_app_event` now handles it (the event arrives as the plain string; an enum-like object with `.name`/`.value` is accepted too): the chat list is reloaded under the plugin lock, the per-chat reply-language cache is dropped, and mode / keep / master / prompt (read live from the settings store) take effect at once. Debounce, cooldown, pending batches and in-flight state are kept.
- A save made by the plugin can no longer overwrite newer external changes: every write re-reads `chats`, applies only the plugin's own change to that one chat (for example `fails`, `enabled` after repeated errors, `title`, `disclosed`) and writes it back. Other chats and other fields edited by the app stay as they are; a chat the app removed is not brought back (only an explicit add creates one).
- The 'Auto' interface language now follows the app language through `client.app_locale()` ('uk', 'ru', 'en'); on apps without that call the previous detection is used. `__min_app_version__` is unchanged (feature-detected).
- Documented in docs/API.md (section 3 next to AppEvent, section 10 storage). No storage format change.

## 0.3.4
- Settings screen restructured. The first section is 'Chats with the bot': one row per chat (title from the app's dialog info; below it mode, on/off and the last decision). Tap a row to open its options (mode, enabled, prompt, reply language, style test, remove), tap again to close. 'Add chat' (chat picker, @username) is right below; everything advanced (general, modes, command, humanize, prompts and model, limits, style test) follows under headers, and 'Recent decisions' is last.
- New owner commands in a private chat (intercepted, never sent, no need to list the chat first): '.ai on' (add and enable, mode Auto), '.ai off' (remove the chat), '.ai status' (state and last decision), '.ai list' (active chats), '.ai mode auto|draft|friend'. Localized uk/ru/en, written to the decision log; groups, channels, bots and secret chats are refused with a message. The chat header menu item is now 'Bot in this chat: on/off' and toggles the same.
- Fix: the bot did not react to messages of a friend in private chats. Private messages arrive as TL_updateShortMessage / TL_updateShortChatMessage, which never become updateNewMessage; the plugin now also listens to these two updates (same pipeline, de-duplicated per chat and message id, so a message that arrives through both paths is answered once). Every message from the other person in a listed chat is written to the decision log as 'received' (no text), so you can see that the plugin got it.
- More reliable autonomous replies: a chat added by any route starts enabled in mode Auto; Balanced preset: silence after you wrote in the chat 45 s (was 2 min), 20 replies per hour per chat (was 12). A message that comes while you are writing is no longer dropped: the reason 'owner_active' is logged and the bot answers after your silence window (up to 2 retries; if you answered yourself meanwhile, it stays silent).
- Reply language follows the chat: Auto (default) takes the language you write in this chat from the last ~15 messages (your own messages decide, a Ukrainian/Russian mix follows your latest message, Ukrainian when there is no signal), cached 10 minutes per chat, and the prompt now names the language explicitly. New 'Reply language' setting (Auto / Ukrainian / Russian / the other person's language), globally and per chat. Applies to auto-replies, '.ai', '.ai <topic>', '.ai ?' and opening phrases (built-in openers in Ukrainian and Russian, chosen by chat language).
- Storage format is unchanged (new optional keys only: rlang_<sk>, reply_lang, decision outcomes 'seen' and 'cmd'); documented in docs/API.md section 10.

## 0.3.3
- Fix: the '.ai' command did nothing and left no trace. The input field always sets an animation object (and often a link-preview object) on a plain text message, and the plugin treated that as an attachment and silently let the message through. Only real attachments (photo, document, location, poll, game, invoice, contact, to-do, retry, video, rich message) are skipped now.
- Every command attempt is in the decision log with a reason: command_disabled, chat_not_listed (sent as a normal message), command_ignored_media, master_off, owner_command_busy, owner_command_* (topic/continue/opener/draft), ai failed, send failed, command_hook_exception.
- Robustness: if the app did not pass an outgoing '.ai' to the plugin before sending (so it reached the chat), the new-message hook now runs the command anyway (logged as owner_command_hook_missed; the '.ai' message itself stays in the chat, the plugin API has no delete call).
- New chat menu item 'AI: write the next message for me' in chats of the plugin: the same command without typing it.
- No app change needed.

## 0.3.2
- Settings screen readable on the phone: 'Recent decisions' is one entry per decision, newest first (title '21:45:30 · Cherish' with the chat name from the plugin list or the app cache, id as fallback; below it the reason in plain language, shown in full and never cut). 'Copy log (last 20)' puts the last 20 decisions on the clipboard, 'Clear log' empties the list.
- Explanatory rows (Modes, hints, style test result, 'No decisions') are no longer tap-looking buttons that do nothing: they use the non-clickable multi-line block. No app change needed; a cleaner API is proposed in docs/API.md 'Core change requests'.
- Localization: settings, hints, decision reasons, bulletins and the menu are in Ukrainian, Russian and English. New 'Interface language' setting (Auto / Українська / Русский / English). zephyr.client has no app-locale call yet, so Auto uses the phone language when Python can see it (uk/ru) and Ukrainian otherwise.
- New: the bot writes first. Type the command (default '.ai' or '.аі', configurable) in a chat of the plugin: the text is cancelled (never sent) and the plugin starts the conversation in your style. '.ai' alone continues the last day's conversation (answers the last unanswered message or gently raises a topic) or, with no fresh context, sends a short opener (editable list, rephrased by the model when Humanize is on); '.ai <topic>' writes the first message about the topic without inventing facts; '.ai ?' / '.ai draft' puts it into the input field instead. Settings: enable, command words, sends/draft, 'Allow in any private chat' (off by default), opener list. Ignores cooldown and hourly limits; every use is in the decision log; sent texts are remembered as plugin texts (no style learning from them, no loop with the new-message hook).

## 0.3.1
- Fix: the bot could stay silent. After the retry the best cleaned reply is now sent anyway (banned words, AI-tell, wrong language); a reply is skipped only when it is empty, emoji-only or identical to our previous reply. A message without a date is no longer dropped. A chat auto-disabled by repeated errors resumes after 30 minutes. Scheduler/process exceptions are caught and logged, and a stuck debounce timer can no longer block a chat.
- Decision log: every sent/skipped decision (reason code, chat id, time; no message text) goes to log.txt and to the 'Recent decisions' item in settings (last 20).
- Presets (Balanced default / Chatty / Quiet), each field editable (empty = preset): debounce 4-6 s with one answer per batch, 20 s between replies, 12 replies/hour per chat with one polite stop line, plain 'ок/дякую/ага/лол' ignored unless a question follows, silent for 2 minutes after you wrote in the chat, groups only for questions/requests, never answers the same message twice, optional quiet hours.
- Typing delay 0.3 s + 25 ms/char, 0.4-2.5 s in total (cap setting 'Typing delay cap'); split only replies over ~120 characters, into at most 2 messages.
- Human text: shorter, stricter prompt; language rule (language of the last message, Ukrainian by default, never Chinese); built-in banned words list (звісно, безумовно, розумію, дійсно, ... and Russian equivalents) plus your own extra words: a reply with them is regenerated once with an explicit instruction, then sent anyway.
- Test style hardened (no stuck 'already running', clear message when nothing to test).

## 0.3.0
- Humanize (new switch, on by default): replies sound like the owner. Strong anti-AI prompt (no assistant filler like "звісно/розумію/як ШІ", no lists/markdown, no intros or summaries, no question back every time, mirror the other person's language, no invented facts). Your own prompt stays as an extra layer; tone presets Neutral / Friendly / Toxic.
- Learn my style: the last 5-50 own outgoing messages (commands, links, long and plugin-sent texts skipped) go to the prompt as examples, plus measured rules (typical length, lowercase start, final period, emoji, slang/swear words, Ukrainian/Russian mix). Cached per chat (default 30 min); chats with few own messages borrow from other added chats. Examples are sent only to your own AI server.
- Delivery: split into 1-3 short messages, typing delay proportional to length with jitter, skip emoji-only messages, max reply length (default 300).
- Generation: temperature 0.95. `max_tokens` and frequency penalty are not exposed by `client.ai_complete`, so the length is limited by prompt and `max_reply`.
- Post-processing: strips markdown, quotes, `Assistant:` prefixes and filler openers; matches the owner's capitalisation, final period and emoji habits; a reply that repeats the previous one or sounds like an AI is regenerated once, then skipped.
- 'Test style': pick a chat (or use the per-chat item) to see 5 sample replies to the last 5 incoming messages; nothing is sent.
- Humanize off keeps the 0.2.0 behavior.

## 0.2.0
- Settings: 'Add chat' section with a chat-list picker and @username / t.me link input (needs an app with `DialogPicker` / `UsernameInput`; older apps keep the chat header menu).
- Friend mode (command mode): the other person triggers the AI with `.ai ` while you stay silent; documented in settings.
- Per-chat list with mode, prompt, enabled switch and Remove chat.

## 0.1.0
- Initial release: per-chat allowlist via the chat header menu, auto / draft / command modes, per-chat prompts, cooldown, daily and hourly caps, loop protection, 3 s debounce.
- Icon: optional; ship a PNG (64 KB max) as `icon.png` next to the plugin, a robot or chat bubble with a spark works well.

## 0.5.3

- Added an opt-in Natural conversation (GLM) profile in Style: GLM replies, DeepSeek helpers, temperature 0.85 and bounded background calls.
- Adaptive reply length: natural conversation no longer forces every sentence into tiny messages.
- Ordinary empathy words no longer trigger paid rewrites or get stripped in this mode. Explicit user bans, language checks and repeat guards still apply.
- Clear automatic-assistant identity when asked directly. Existing chat, media, voice and memory permissions are preserved.
- Existing installations keep their settings until the profile is enabled. Covered by 600 local tests; plugin validation and index build pass.

