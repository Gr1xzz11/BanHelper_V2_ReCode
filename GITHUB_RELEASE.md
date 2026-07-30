# Публикация BanHelper на GitHub

Эта папка подготовлена как чистый GitHub-проект: пользовательские базы,
логи, виртуальные окружения и временные каталоги сборки в неё не включены.

## Что находится в проекте

- исходный код BanHelper;
- исходный код Fabric-мода;
- тесты и benchmark;
- Linux/Windows build-скрипты;
- GitHub Actions workflow для Windows;
- документация протокола;
- скриншоты;
- каталог `release-assets` с готовыми файлами релиза.

## Рекомендуемый порядок публикации

1. Создайте на GitHub новый пустой репозиторий `BanHelper`.
2. Не добавляйте при создании GitHub README, `.gitignore` или лицензию:
   необходимые файлы уже находятся в папке.
3. Откройте терминал внутри `readyToGithub`.
4. Выполните:

```bash
git init
git add .
git commit -m "BanHelper 2.0 release"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/BanHelper.git
git push -u origin main
```

## Windows EXE через GitHub Actions

После первого push:

1. Откройте вкладку **Actions**.
2. Выберите **Build Windows release**.
3. Нажмите **Run workflow**.
4. Дождитесь зелёного статуса.
5. Скачайте artifact `BanHelper-Windows`.

Workflow собирает и проверяет `dist/windows/BanHelper.exe` на настоящем
Windows runner. Не публикуйте EXE как проверенный, если workflow завершился
ошибкой.

## Создание GitHub Release

1. Откройте **Releases → Draft a new release**.
2. Создайте тег `v2.0.1`.
3. Название: `BanHelper 2.0.1`.
4. Приложите из `release-assets`:

   - `BanHelper.grxt`;
   - `banhelper-bridge-2.0.0.jar`;
   - `BanHelper2-final-release.zip`;
   - Windows `BanHelper.exe` после успешного Actions workflow;
   - `SHA256SUMS.txt`.

5. В описание релиза можно вставить содержимое `RELEASE.md`.

## Linux

```bash
chmod +x BanHelper.grxt
./BanHelper.grxt
```

## Важно

- Fabric JAR предназначен для Minecraft 1.21.4 Fabric.
- Desktop BanHelper не требует Python или Java.
- Java 21 требуется самому Minecraft/Fabric и обычно поставляется launcher.
- Не публикуйте пользовательские `.sqlite3`, конфиги с токенами или логи.
- Windows EXE должен собираться на Windows, а Linux `.grxt` — на Linux.
