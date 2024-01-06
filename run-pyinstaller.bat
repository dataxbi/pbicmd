
:: Ejecuta pyinstaller para crear el ejecutable pbicmd.exe a partir del script pbicmd.py
:: El resultado estará en la carpeta dist.
:: Luego crea en la misma carpeta dist el fichero ZIP pbicmd.%Version%.zip
:: donde %Version% la lee del fichero version.py

pyinstaller ^
    --hidden-import=pyarrow ^
    --onefile ^
    --clean ^
    --noconfirm ^
    pbicmd.py

".\.venv\scripts\python.exe" _version.py > dist/version.txt
set /p Version=<dist/version.txt

cd dist
del version.txt
del *.zip
"C:\Program Files\7-Zip\7z.exe" -tzip a  pbicmd.%Version%.zip pbicmd.exe
cd ..
