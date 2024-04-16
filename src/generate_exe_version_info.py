from _version import __version__

version_comma = __version__.replace('.',',')

print(f'''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_comma},0),
    prodvers=({version_comma},0),
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'dataXbi'),
        StringStruct(u'FileDescription', u'CLI para Power BI y Fabric'),
        StringStruct(u'FileVersion', u'{__version__}'),
        StringStruct(u'InternalName', u'pbicmd'),
        StringStruct(u'OriginalFilename', u'pbicmd.exe'),
        StringStruct(u'ProductName', u'pbicmd'),
        StringStruct(u'ProductVersion', u'{version_comma}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [4096, 1200])])      
  ]
)
''')