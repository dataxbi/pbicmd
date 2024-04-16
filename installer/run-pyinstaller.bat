
:: Ejecuta pyinstaller para crear el ejecutable pbicmd.exe a partir del script pbicmd.py
:: El resultado estará en la carpeta dist.
:: Luego crea en la misma carpeta dist el fichero ZIP pbicmd.%Version%.zip
:: donde %Version% la lee del fichero version.py

"..\.venv\scripts\python.exe" ../src/generate_exe_version_info.py > dist/exe_version_info.txt

pyinstaller ^
    --hidden-import=pyarrow ^
    --onefile ^
    --clean ^
    --noconfirm ^
    --icon icon.ico ^
    --version-file dist/exe_version_info.txt ^
    ../src/pbicmd.py


"..\.venv\scripts\python.exe" ../src/_version.py > dist/version.txt
set /p Version=<dist/version.txt

cd dist
del version.txt
del exe_version_info.txt
del *.zip
"C:\Program Files\7-Zip\7z.exe" -tzip a  pbicmd.%Version%.zip pbicmd.exe
certutil -hashfile .\pbicmd.%Version%.zip SHA256
cd ..
