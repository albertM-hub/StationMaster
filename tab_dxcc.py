"""
tab_dxcc.py — Onglet unifié DX World + DXCC pour Station Master (ON5AM)
340 entités DXCC officielles ARRL avec gestion confirmations/LoTW.
Importé par station_master.py : DXCCTab(parent, app, get_country, grid_to_latlon)
"""
import math
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

# ── 340 entités DXCC (source : cty.dat ARRL) ─────────────────────────────────
DXCC_DATA = [
    # Europe
    ("OH0"         , "Aland Islands"                           , "EU",   60.1,    20.4),
    ("ZA"          , "Albania"                                 , "EU",   41.0,    20.0),
    ("C3"          , "Andorra"                                 , "EU",   42.6,     1.6),
    ("OE"          , "Austria"                                 , "EU",   47.3,    13.3),
    ("CU"          , "Azores"                                  , "EU",   38.7,   -27.2),
    ("EA6"         , "Balearic Islands"                        , "EU",   39.6,     3.0),
    ("EU"          , "Belarus"                                 , "EU",   54.0,    28.0),
    ("ON"          , "Belgium"                                 , "EU",   50.7,     4.8),
    ("E7"          , "Bosnia-Herzegovina"                      , "EU",   44.3,    17.6),
    ("LZ"          , "Bulgaria"                                , "EU",   42.8,    25.1),
    ("TK"          , "Corsica"                                 , "EU",   42.0,     9.0),
    ("SV9"         , "Crete"                                   , "EU",   35.2,    24.8),
    ("9A"          , "Croatia"                                 , "EU",   45.2,    15.3),
    ("OK"          , "Czech Republic"                          , "EU",   50.0,    16.0),
    ("OZ"          , "Denmark"                                 , "EU",   56.0,    10.0),
    ("SV5"         , "Dodecanese"                              , "EU",   36.2,    27.9),
    ("G"           , "England"                                 , "EU",   52.8,    -1.5),
    ("ES"          , "Estonia"                                 , "EU",   59.0,    25.0),
    ("UA"          , "European Russia"                         , "EU",   53.6,    41.4),
    ("OY"          , "Faroe Islands"                           , "EU",   62.1,    -6.9),
    ("DL"          , "Fed. Rep. of Germany"                    , "EU",   51.0,    10.0),
    ("OH"          , "Finland"                                 , "EU",   61.4,    24.8),
    ("F"           , "France"                                  , "EU",   46.0,     2.0),
    ("R1FJ"        , "Franz Josef Land"                        , "EU",   80.7,    49.9),
    ("ZB"          , "Gibraltar"                               , "EU",   36.1,    -5.4),
    ("SV"          , "Greece"                                  , "EU",   39.8,    21.8),
    ("GU"          , "Guernsey"                                , "EU",   49.5,    -2.6),
    ("HA"          , "Hungary"                                 , "EU",   47.1,    19.3),
    ("4U1I"        , "ITU HQ"                                  , "EU",   46.2,     6.0),
    ("TF"          , "Iceland"                                 , "EU",   64.8,   -18.7),
    ("EI"          , "Ireland"                                 , "EU",   53.1,    -8.0),
    ("GD"          , "Isle of Man"                             , "EU",   54.2,    -4.5),
    ("I"           , "Italy"                                   , "EU",   42.8,    12.6),
    ("JX"          , "Jan Mayen"                               , "EU",   71.0,    -8.3),
    ("GJ"          , "Jersey"                                  , "EU",   49.2,    -2.2),
    ("UA2"         , "Kaliningrad"                             , "EU",   54.7,    20.5),
    ("YL"          , "Latvia"                                  , "EU",   57.0,    24.6),
    ("HB0"         , "Liechtenstein"                           , "EU",   47.1,     9.6),
    ("LY"          , "Lithuania"                               , "EU",   55.5,    23.6),
    ("LX"          , "Luxembourg"                              , "EU",   50.0,     6.0),
    ("9H"          , "Malta"                                   , "EU",   35.9,    14.4),
    ("OJ0"         , "Market Reef"                             , "EU",   60.0,    19.0),
    ("ER"          , "Moldova"                                 , "EU",   47.0,    29.0),
    ("3A"          , "Monaco"                                  , "EU",   43.7,     7.4),
    ("4O"          , "Montenegro"                              , "EU",   42.5,    19.3),
    ("SV/a"        , "Mount Athos"                             , "EU",   40.0,    24.0),
    ("PA"          , "Netherlands"                             , "EU",   52.3,     5.5),
    ("Z3"          , "North Macedonia"                         , "EU",   41.6,    21.6),
    ("GI"          , "Northern Ireland"                        , "EU",   54.7,    -6.7),
    ("LA"          , "Norway"                                  , "EU",   61.0,     9.0),
    ("SP"          , "Poland"                                  , "EU",   52.3,    18.7),
    ("CT"          , "Portugal"                                , "EU",   39.5,    -8.0),
    ("Z6"          , "Republic of Kosovo"                      , "EU",   42.7,    21.2),
    ("YO"          , "Romania"                                 , "EU",   45.8,    24.7),
    ("T7"          , "San Marino"                              , "EU",   44.0,    12.4),
    ("IS"          , "Sardinia"                                , "EU",   40.1,     9.3),
    ("GM"          , "Scotland"                                , "EU",   56.8,    -4.2),
    ("YU"          , "Serbia"                                  , "EU",   44.0,    21.0),
    ("OM"          , "Slovak Republic"                         , "EU",   49.0,    20.0),
    ("S5"          , "Slovenia"                                , "EU",   46.0,    14.0),
    ("1A"          , "Sov Mil Order of Malta"                  , "EU",   41.9,    12.4),
    ("EA"          , "Spain"                                   , "EU",   40.3,    -3.4),
    ("JW"          , "Svalbard"                                , "EU",   78.0,    16.0),
    ("SM"          , "Sweden"                                  , "EU",   58.9,    15.3),
    ("HB"          , "Switzerland"                             , "EU",   46.9,     8.1),
    ("UR"          , "Ukraine"                                 , "EU",   50.0,    30.0),
    ("HV"          , "Vatican City"                            , "EU",   41.9,    12.5),
    ("GW"          , "Wales"                                   , "EU",   52.3,    -3.7),
    # Asie
    ("YA"          , "Afghanistan"                             , "AS",   34.7,    65.8),
    ("VU4"         , "Andaman & Nicobar Is."                   , "AS",   12.4,    92.8),
    ("EK"          , "Armenia"                                 , "AS",   40.4,    44.9),
    ("UA9"         , "Asiatic Russia"                          , "AS",   55.9,    84.1),
    ("TA"          , "Asiatic Turkey"                          , "AS",   39.2,    35.6),
    ("4J"          , "Azerbaijan"                              , "AS",   40.5,    47.4),
    ("A9"          , "Bahrain"                                 , "AS",   26.0,    50.5),
    ("S2"          , "Bangladesh"                              , "AS",   24.1,    89.7),
    ("A5"          , "Bhutan"                                  , "AS",   27.4,    90.2),
    ("XU"          , "Cambodia"                                , "AS",   12.9,   105.1),
    ("BY"          , "China"                                   , "AS",   36.0,   102.0),
    ("5B"          , "Cyprus"                                  , "AS",   35.0,    33.0),
    ("P5"          , "DPR of Korea"                            , "AS",   39.8,   126.3),
    ("4L"          , "Georgia"                                 , "AS",   42.0,    45.0),
    ("VR"          , "Hong Kong"                               , "AS",   22.3,   114.2),
    ("VU"          , "India"                                   , "AS",   22.5,    77.6),
    ("EP"          , "Iran"                                    , "AS",   32.0,    53.0),
    ("YI"          , "Iraq"                                    , "AS",   33.9,    42.8),
    ("4X"          , "Israel"                                  , "AS",   31.3,    34.8),
    ("JA"          , "Japan"                                   , "AS",   36.4,   138.4),
    ("JY"          , "Jordan"                                  , "AS",   31.2,    36.4),
    ("UN"          , "Kazakhstan"                              , "AS",   48.2,    65.2),
    ("9K"          , "Kuwait"                                  , "AS",   29.4,    47.4),
    ("EX"          , "Kyrgyzstan"                              , "AS",   41.7,    74.1),
    ("VU7"         , "Lakshadweep Islands"                     , "AS",   11.2,    72.8),
    ("XW"          , "Laos"                                    , "AS",   18.2,   104.5),
    ("OD"          , "Lebanon"                                 , "AS",   33.8,    35.8),
    ("XX9"         , "Macao"                                   , "AS",   22.1,   113.5),
    ("8Q"          , "Maldives"                                , "AS",    4.2,    73.5),
    ("JT"          , "Mongolia"                                , "AS",   46.8,   102.2),
    ("XZ"          , "Myanmar"                                 , "AS",   20.0,    96.4),
    ("9N"          , "Nepal"                                   , "AS",   27.7,    85.3),
    ("JD/o"        , "Ogasawara"                               , "AS",   27.1,   142.2),
    ("A4"          , "Oman"                                    , "AS",   23.6,    58.5),
    ("AP"          , "Pakistan"                                , "AS",   30.0,    70.0),
    ("E4"          , "Palestine"                               , "AS",   31.3,    34.3),
    ("BV9P"        , "Pratas Island"                           , "AS",   20.7,   116.7),
    ("A7"          , "Qatar"                                   , "AS",   25.2,    51.1),
    ("HL"          , "Republic of Korea"                       , "AS",   36.2,   127.9),
    ("HZ"          , "Saudi Arabia"                            , "AS",   24.2,    43.8),
    ("BS7"         , "Scarborough Reef"                        , "AS",   15.1,   117.7),
    ("9V"          , "Singapore"                               , "AS",    1.4,   103.8),
    ("1S"          , "Spratly Islands"                         , "AS",    9.9,   114.2),
    ("4S"          , "Sri Lanka"                               , "AS",    7.6,    80.7),
    ("YK"          , "Syria"                                   , "AS",   35.4,    38.2),
    ("BV"          , "Taiwan"                                  , "AS",   23.7,   120.9),
    ("EY"          , "Tajikistan"                              , "AS",   38.8,    71.2),
    ("HS"          , "Thailand"                                , "AS",   12.6,    99.7),
    ("EZ"          , "Turkmenistan"                            , "AS",   38.0,    58.0),
    ("ZC4"         , "UK Base Areas on Cyprus"                 , "AS",   35.3,    33.6),
    ("A6"          , "United Arab Emirates"                    , "AS",   24.0,    54.0),
    ("UK"          , "Uzbekistan"                              , "AS",   41.4,    64.0),
    ("3W"          , "Vietnam"                                 , "AS",   15.8,   107.9),
    ("9M2"         , "West Malaysia"                           , "AS",    4.0,   102.2),
    ("7O"          , "Yemen"                                   , "AS",   15.7,    48.1),
    # Afrique
    ("3B6"         , "Agalega & St. Brandon"                   , "AF",  -10.4,    56.7),
    ("7X"          , "Algeria"                                 , "AF",   28.0,     2.0),
    ("FT/z"        , "Amsterdam & St. Paul Is."                , "AF",  -37.9,    77.5),
    ("D2"          , "Angola"                                  , "AF",  -12.5,    18.5),
    ("3C0"         , "Annobon Island"                          , "AF",   -1.4,     5.6),
    ("ZD8"         , "Ascension Island"                        , "AF",   -7.9,   -14.4),
    ("TY"          , "Benin"                                   , "AF",    9.9,     2.2),
    ("A2"          , "Botswana"                                , "AF",  -22.0,    24.0),
    ("3Y/b"        , "Bouvet"                                  , "AF",  -54.4,     3.4),
    ("XT"          , "Burkina Faso"                            , "AF",   12.0,    -2.0),
    ("9U"          , "Burundi"                                 , "AF",   -3.2,    29.8),
    ("TJ"          , "Cameroon"                                , "AF",    5.4,    11.9),
    ("EA8"         , "Canary Islands"                          , "AF",   28.3,   -15.8),
    ("D4"          , "Cape Verde"                              , "AF",   16.0,   -24.0),
    ("TL"          , "Central African Republic"                , "AF",    6.8,    20.3),
    ("EA9"         , "Ceuta & Melilla"                         , "AF",   35.9,    -5.3),
    ("TT"          , "Chad"                                    , "AF",   15.8,    18.2),
    ("VQ9"         , "Chagos Islands"                          , "AF",   -7.3,    72.4),
    ("D6"          , "Comoros"                                 , "AF",  -11.6,    43.3),
    ("TU"          , "Cote d'Ivoire"                           , "AF",    7.6,    -5.8),
    ("FT/w"        , "Crozet Island"                           , "AF",  -46.4,    51.8),
    ("9Q"          , "Dem. Rep. of the Congo"                  , "AF",   -3.1,    23.0),
    ("J2"          , "Djibouti"                                , "AF",   11.8,    42.4),
    ("SU"          , "Egypt"                                   , "AF",   26.3,    28.6),
    ("3C"          , "Equatorial Guinea"                       , "AF",    1.7,    10.3),
    ("E3"          , "Eritrea"                                 , "AF",   15.0,    39.0),
    ("ET"          , "Ethiopia"                                , "AF",    9.0,    39.0),
    ("TR"          , "Gabon"                                   , "AF",   -0.4,    11.7),
    ("9G"          , "Ghana"                                   , "AF",    7.7,    -1.6),
    ("FT/g"        , "Glorioso Islands"                        , "AF",  -11.6,    47.3),
    ("3X"          , "Guinea"                                  , "AF",   11.0,   -10.7),
    ("J5"          , "Guinea-Bissau"                           , "AF",   12.0,   -14.8),
    ("VK0H"        , "Heard Island"                            , "AF",  -53.1,    73.5),
    ("FT/j"        , "Juan de Nova, Europa"                    , "AF",  -17.1,    42.7),
    ("5Z"          , "Kenya"                                   , "AF",    0.3,    38.1),
    ("FT/x"        , "Kerguelen Islands"                       , "AF",  -49.0,    69.3),
    ("3DA"         , "Kingdom of Eswatini"                     , "AF",  -26.6,    31.5),
    ("7P"          , "Lesotho"                                 , "AF",  -29.2,    27.9),
    ("EL"          , "Liberia"                                 , "AF",    6.5,    -9.5),
    ("5A"          , "Libya"                                   , "AF",   27.2,    16.6),
    ("5R"          , "Madagascar"                              , "AF",  -19.0,    46.6),
    ("CT3"         , "Madeira Islands"                         , "AF",   32.8,   -16.9),
    ("7Q"          , "Malawi"                                  , "AF",  -14.0,    34.0),
    ("TZ"          , "Mali"                                    , "AF",   18.0,    -2.6),
    ("5T"          , "Mauritania"                              , "AF",   20.6,   -10.5),
    ("3B8"         , "Mauritius"                               , "AF",  -20.4,    57.5),
    ("FH"          , "Mayotte"                                 , "AF",  -12.9,    45.1),
    ("CN"          , "Morocco"                                 , "AF",   32.0,    -5.0),
    ("C9"          , "Mozambique"                              , "AF",  -18.2,    35.0),
    ("V5"          , "Namibia"                                 , "AF",  -22.0,    17.0),
    ("5U"          , "Niger"                                   , "AF",   17.6,     9.4),
    ("5N"          , "Nigeria"                                 , "AF",    9.9,     7.5),
    ("ZS8"         , "Pr. Edward & Marion Is."                 , "AF",  -46.9,    37.7),
    ("Z8"          , "Republic of South Sudan"                 , "AF",    4.8,    31.6),
    ("TN"          , "Republic of the Congo"                   , "AF",   -1.0,    15.4),
    ("FR"          , "Reunion Island"                          , "AF",  -21.1,    55.5),
    ("3B9"         , "Rodriguez Island"                        , "AF",  -19.7,    63.4),
    ("9X"          , "Rwanda"                                  , "AF",   -1.8,    29.8),
    ("S9"          , "Sao Tome & Principe"                     , "AF",    0.2,     6.6),
    ("6W"          , "Senegal"                                 , "AF",   15.2,   -14.6),
    ("S7"          , "Seychelles"                              , "AF",   -4.7,    55.5),
    ("9L"          , "Sierra Leone"                            , "AF",    8.5,   -13.2),
    ("T5"          , "Somalia"                                 , "AF",    2.0,    45.4),
    ("ZS"          , "South Africa"                            , "AF",  -29.1,    22.6),
    ("ZD7"         , "St. Helena"                              , "AF",  -16.0,    -5.7),
    ("ST"          , "Sudan"                                   , "AF",   14.5,    28.6),
    ("5H"          , "Tanzania"                                , "AF",   -5.8,    33.9),
    ("C5"          , "The Gambia"                              , "AF",   13.4,   -16.4),
    ("5V"          , "Togo"                                    , "AF",    8.4,     1.3),
    ("ZD9"         , "Tristan da Cunha & Gough"                , "AF",  -37.1,   -12.3),
    ("FT/t"        , "Tromelin Island"                         , "AF",  -15.9,    54.5),
    ("3V"          , "Tunisia"                                 , "AF",   35.4,     9.3),
    ("5X"          , "Uganda"                                  , "AF",    1.9,    32.6),
    ("S0"          , "Western Sahara"                          , "AF",   24.8,   -13.8),
    ("9J"          , "Zambia"                                  , "AF",  -14.2,    26.7),
    ("Z2"          , "Zimbabwe"                                , "AF",  -18.0,    31.0),
    # Am. Nord
    ("KL"          , "Alaska"                                  , "NA",   61.4,  -148.9),
    ("VP2E"        , "Anguilla"                                , "NA",   18.2,   -63.0),
    ("V2"          , "Antigua & Barbuda"                       , "NA",   17.1,   -61.8),
    ("YV0"         , "Aves Island"                             , "NA",   15.7,   -63.6),
    ("C6"          , "Bahamas"                                 , "NA",   24.2,   -76.0),
    ("8P"          , "Barbados"                                , "NA",   13.2,   -59.5),
    ("V3"          , "Belize"                                  , "NA",   17.0,   -88.7),
    ("VP9"         , "Bermuda"                                 , "NA",   32.3,   -64.7),
    ("VP2V"        , "British Virgin Islands"                  , "NA",   18.3,   -64.8),
    ("VE"          , "Canada"                                  , "NA",   44.4,   -78.8),
    ("ZF"          , "Cayman Islands"                          , "NA",   19.3,   -81.2),
    ("FO/c"        , "Clipperton Island"                       , "NA",   10.3,  -109.2),
    ("TI9"         , "Cocos Island"                            , "NA",    5.5,   -87.0),
    ("TI"          , "Costa Rica"                              , "NA",   10.0,   -84.0),
    ("CM"          , "Cuba"                                    , "NA",   21.5,   -80.0),
    ("KP5"         , "Desecheo Island"                         , "NA",   18.1,   -67.9),
    ("J7"          , "Dominica"                                , "NA",   15.4,   -61.4),
    ("HI"          , "Dominican Republic"                      , "NA",   19.1,   -70.7),
    ("YS"          , "El Salvador"                             , "NA",   14.0,   -89.0),
    ("OX"          , "Greenland"                               , "NA",   74.0,   -42.8),
    ("J3"          , "Grenada"                                 , "NA",   12.1,   -61.7),
    ("FG"          , "Guadeloupe"                              , "NA",   16.1,   -61.7),
    ("KG4"         , "Guantanamo Bay"                          , "NA",   20.0,   -75.0),
    ("TG"          , "Guatemala"                               , "NA",   15.5,   -90.3),
    ("HH"          , "Haiti"                                   , "NA",   19.0,   -72.2),
    ("HR"          , "Honduras"                                , "NA",   15.0,   -87.0),
    ("6Y"          , "Jamaica"                                 , "NA",   18.2,   -77.5),
    ("FM"          , "Martinique"                              , "NA",   14.7,   -61.0),
    ("XE"          , "Mexico"                                  , "NA",   21.3,  -100.2),
    ("VP2M"        , "Montserrat"                              , "NA",   16.8,   -62.2),
    ("KP1"         , "Navassa Island"                          , "NA",   18.4,   -75.0),
    ("YN"          , "Nicaragua"                               , "NA",   12.9,   -85.0),
    ("HP"          , "Panama"                                  , "NA",    9.0,   -80.0),
    ("KP4"         , "Puerto Rico"                             , "NA",   18.2,   -66.5),
    ("XF4"         , "Revillagigedo"                           , "NA",   18.8,  -111.0),
    ("PJ5"         , "Saba & St. Eustatius"                    , "NA",   17.6,   -63.1),
    ("CY0"         , "Sable Island"                            , "NA",   43.9,   -59.9),
    ("HK0/a"       , "San Andres & Providencia"                , "NA",   12.6,   -81.7),
    ("PJ7"         , "Sint Maarten"                            , "NA",   18.1,   -63.1),
    ("FJ"          , "St. Barthelemy"                          , "NA",   17.9,   -62.8),
    ("V4"          , "St. Kitts & Nevis"                       , "NA",   17.4,   -62.8),
    ("J6"          , "St. Lucia"                               , "NA",   13.9,   -61.0),
    ("FS"          , "St. Martin"                              , "NA",   18.1,   -63.0),
    ("CY9"         , "St. Paul Island"                         , "NA",   47.0,   -60.0),
    ("FP"          , "St. Pierre & Miquelon"                   , "NA",   46.8,   -56.2),
    ("J8"          , "St. Vincent"                             , "NA",   13.2,   -61.2),
    ("VP5"         , "Turks & Caicos Islands"                  , "NA",   21.8,   -71.8),
    ("KP2"         , "US Virgin Islands"                       , "NA",   17.7,   -64.8),
    ("4U1U"        , "United Nations HQ"                       , "NA",   40.8,   -74.0),
    ("K"           , "United States"                           , "NA",   37.6,   -91.9),
    # Am. Sud
    ("LU"          , "Argentina"                               , "SA",  -32.5,   -62.1),
    ("P4"          , "Aruba"                                   , "SA",   12.5,   -70.0),
    ("CP"          , "Bolivia"                                 , "SA",  -17.0,   -65.0),
    ("PJ4"         , "Bonaire"                                 , "SA",   12.2,   -68.2),
    ("PY"          , "Brazil"                                  , "SA",  -10.0,   -53.0),
    ("CE"          , "Chile"                                   , "SA",  -30.0,   -71.0),
    ("HK"          , "Colombia"                                , "SA",    5.0,   -74.0),
    ("PJ2"         , "Curacao"                                 , "SA",   12.2,   -69.0),
    ("CE0Y"        , "Easter Island"                           , "SA",  -27.1,  -109.4),
    ("HC"          , "Ecuador"                                 , "SA",   -1.4,   -78.4),
    ("VP8"         , "Falkland Islands"                        , "SA",  -51.6,   -58.7),
    ("PY0F"        , "Fernando de Noronha"                     , "SA",   -3.9,   -32.4),
    ("FY"          , "French Guiana"                           , "SA",    4.0,   -53.0),
    ("HC8"         , "Galapagos Islands"                       , "SA",   -0.8,   -91.0),
    ("8R"          , "Guyana"                                  , "SA",    6.0,   -59.5),
    ("CE0Z"        , "Juan Fernandez Islands"                  , "SA",  -33.6,   -78.8),
    ("HK0/m"       , "Malpelo Island"                          , "SA",    4.0,   -81.6),
    ("ZP"          , "Paraguay"                                , "SA",  -25.3,   -57.7),
    ("OA"          , "Peru"                                    , "SA",  -10.0,   -76.0),
    ("3Y/p"        , "Peter 1 Island"                          , "SA",  -68.8,   -90.6),
    ("CE0X"        , "San Felix & San Ambrosio"                , "SA",  -26.3,   -80.1),
    ("VP8/g"       , "South Georgia Island"                    , "SA",  -54.5,   -37.1),
    ("VP8/o"       , "South Orkney Islands"                    , "SA",  -60.6,   -45.5),
    ("VP8/s"       , "South Sandwich Islands"                  , "SA",  -58.4,   -26.3),
    ("VP8/h"       , "South Shetland Islands"                  , "SA",  -62.1,   -58.7),
    ("PY0S"        , "St. Peter & St. Paul"                    , "SA",    0.0,   -29.0),
    ("PZ"          , "Suriname"                                , "SA",    4.0,   -56.0),
    ("PY0T"        , "Trindade & Martim Vaz"                   , "SA",  -20.5,   -29.3),
    ("9Y"          , "Trinidad & Tobago"                       , "SA",   10.4,   -61.3),
    ("CX"          , "Uruguay"                                 , "SA",  -33.0,   -56.0),
    ("YV"          , "Venezuela"                               , "SA",    8.0,   -66.0),
    # Océanie
    ("KH8"         , "American Samoa"                          , "OC",  -14.3,  -170.8),
    ("FO/a"        , "Austral Islands"                         , "OC",  -23.4,  -149.5),
    ("VK"          , "Australia"                               , "OC",  -23.7,   132.3),
    ("KH1"         , "Baker & Howland Islands"                 , "OC",    0.0,  -176.0),
    ("T33"         , "Banaba Island"                           , "OC",   -0.9,   169.5),
    ("V8"          , "Brunei Darussalam"                       , "OC",    4.5,   114.6),
    ("T31"         , "Central Kiribati"                        , "OC",   -2.8,  -171.7),
    ("ZL7"         , "Chatham Islands"                         , "OC",  -43.9,  -176.5),
    ("FK/c"        , "Chesterfield Islands"                    , "OC",  -19.9,   158.3),
    ("VK9X"        , "Christmas Island"                        , "OC",  -10.5,   105.6),
    ("VK9C"        , "Cocos (Keeling) Islands"                 , "OC",  -12.2,    96.8),
    ("3D2/c"       , "Conway Reef"                             , "OC",  -22.0,   175.0),
    ("VP6/d"       , "Ducie Island"                            , "OC",  -24.7,  -124.8),
    ("9M6"         , "East Malaysia"                           , "OC",    2.7,   113.3),
    ("T32"         , "Eastern Kiribati"                        , "OC",    1.8,  -157.3),
    ("3D2"         , "Fiji"                                    , "OC",  -17.8,   177.9),
    ("FO"          , "French Polynesia"                        , "OC",  -17.6,  -149.4),
    ("KH2"         , "Guam"                                    , "OC",   13.4,   144.7),
    ("KH6"         , "Hawaii"                                  , "OC",   21.1,  -157.5),
    ("YB"          , "Indonesia"                               , "OC",   -7.3,   109.9),
    ("KH3"         , "Johnston Island"                         , "OC",   16.7,  -169.5),
    ("ZL8"         , "Kermadec Islands"                        , "OC",  -29.2,  -177.9),
    ("KH7K"        , "Kure Island"                             , "OC",   29.0,  -178.0),
    ("VK9L"        , "Lord Howe Island"                        , "OC",  -31.6,   159.1),
    ("VK0M"        , "Macquarie Island"                        , "OC",  -54.6,   158.9),
    ("KH0"         , "Mariana Islands"                         , "OC",   15.2,   145.7),
    ("FO/m"        , "Marquesas Islands"                       , "OC",   -8.9,  -140.1),
    ("V7"          , "Marshall Islands"                        , "OC",    9.1,   167.3),
    ("VK9M"        , "Mellish Reef"                            , "OC",  -17.4,   155.8),
    ("V6"          , "Micronesia"                              , "OC",    6.9,   158.2),
    ("KH4"         , "Midway Island"                           , "OC",   28.2,  -177.4),
    ("JD/m"        , "Minami Torishima"                        , "OC",   24.3,   154.0),
    ("ZL9"         , "N.Z. Subantarctic Is."                   , "OC",  -51.6,   167.6),
    ("C2"          , "Nauru"                                   , "OC",   -0.5,   166.9),
    ("FK"          , "New Caledonia"                           , "OC",  -21.5,   165.5),
    ("ZL"          , "New Zealand"                             , "OC",  -39.0,   174.5),
    ("E6"          , "Niue"                                    , "OC",  -19.0,  -169.8),
    ("VK9N"        , "Norfolk Island"                          , "OC",  -29.0,   167.9),
    ("E5/n"        , "North Cook Islands"                      , "OC",  -10.0,  -161.1),
    ("T8"          , "Palau"                                   , "OC",    7.5,   134.5),
    ("KH5"         , "Palmyra & Jarvis Islands"                , "OC",    5.9,  -162.1),
    ("P2"          , "Papua New Guinea"                        , "OC",   -9.5,   147.1),
    ("DU"          , "Philippines"                             , "OC",   13.0,   122.0),
    ("VP6"         , "Pitcairn Island"                         , "OC",  -25.1,  -130.1),
    ("3D2/r"       , "Rotuma Island"                           , "OC",  -12.5,   177.1),
    ("5W"          , "Samoa"                                   , "OC",  -13.9,  -171.7),
    ("H4"          , "Solomon Islands"                         , "OC",   -9.0,   160.0),
    ("E5/s"        , "South Cook Islands"                      , "OC",  -21.9,  -157.9),
    ("KH8/s"       , "Swains Island"                           , "OC",  -11.1,  -171.2),
    ("H40"         , "Temotu Province"                         , "OC",  -10.7,   165.8),
    ("4W"          , "Timor - Leste"                           , "OC",   -8.8,   126.0),
    ("ZK3"         , "Tokelau Islands"                         , "OC",   -9.4,  -171.2),
    ("A3"          , "Tonga"                                   , "OC",  -21.2,  -175.1),
    ("T2"          , "Tuvalu"                                  , "OC",   -8.5,   179.2),
    ("YJ"          , "Vanuatu"                                 , "OC",  -17.7,   168.4),
    ("KH9"         , "Wake Island"                             , "OC",   19.3,   166.6),
    ("FW"          , "Wallis & Futuna Islands"                 , "OC",  -13.3,  -176.2),
    ("T30"         , "Western Kiribati"                        , "OC",    1.4,   173.0),
    ("VK9W"        , "Willis Island"                           , "OC",  -16.2,   150.0),
    # Antarctique
    ("CE9"         , "Antarctica"                              , "AN",  -90.0,    -0.0),
]

CONTINENT_NAMES = {
    "EU": "Europe", "AS": "Asie", "AF": "Afrique",
    "NA": "Am. Nord", "SA": "Am. Sud", "OC": "Océanie", "AN": "Antarctique"
}

_COLS = ("Préfixe", "Entité DXCC", "Continent", "Dist. km",
         "Short Path°", "Long Path°", "QSOs", "Bandes", "1er QSO", "Statut", "Notes")
_COL_W = (70, 190, 82, 72, 82, 82, 52, 130, 88, 105, 160)
_COL_KEY = {
    "Préfixe": "prefix", "Entité DXCC": "entity", "Continent": "cont",
    "Dist. km": "dist", "Short Path°": "short", "Long Path°": "long",
    "QSOs": "qsos", "Bandes": "bands", "1er QSO": "first_date",
    "Statut": "statut", "Notes": "notes",
}


class DXCCTab:
    """Onglet unifié DX World + DXCC."""

    def __init__(self, parent, app, get_country=None, grid_to_latlon=None):
        self.app           = app
        self.conn          = app.conn
        self.root          = app.root
        self._get_country  = get_country  or (lambda c: None)
        self._grid_latlon  = grid_to_latlon or (lambda g: None)
        self._rows         = []   # liste complète pré-calculée
        self._sort_col_key = "entity"
        self._sort_rev     = False
        self._build(parent)
        self.root.after(200, self.refresh)

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build(self, parent):
        # Boutons d'action
        btn_fr = tk.Frame(parent, bg="#11273f"); btn_fr.pack(fill="x", pady=(2, 0))
        ttk.Button(btn_fr, text="🔄 Recalculer",
                   command=self.refresh, bootstyle="primary").pack(side="left", padx=(5,2))
        ttk.Button(btn_fr, text="✅ Marquer confirmé",
                   command=self.confirm_selection, bootstyle="success-outline").pack(side="left", padx=2)
        ttk.Button(btn_fr, text="❌ Retirer confirmation",
                   command=self.unconfirm_selection, bootstyle="danger-outline").pack(side="left", padx=2)
        ttk.Button(btn_fr, text="📤 Export ADIF LoTW",
                   command=self.app.export_lotw_adif, bootstyle="info-outline").pack(side="left", padx=2)
        ttk.Button(btn_fr, text="📡 Soumettre LoTW (auto)",
                   command=self.app._submit_lotw_direct, bootstyle="success-outline").pack(side="left", padx=2)

        self._info_var = tk.StringVar(value="")
        ttk.Label(btn_fr, textvariable=self._info_var,
                  font=("Consolas", 10, "bold"), foreground="#f39c12").pack(side="right", padx=10)

        # Barre de filtres
        flt = tk.Frame(parent, bg="#11273f"); flt.pack(fill="x", pady=1)

        ttk.Label(flt, text="Recherche:").pack(side="left", padx=(5,2))
        self._search_var = tk.StringVar()
        e = ttk.Entry(flt, textvariable=self._search_var, width=16)
        e.pack(side="left", padx=2)
        e.bind("<KeyRelease>", lambda _e: self._filter())

        ttk.Label(flt, text="Continent:").pack(side="left", padx=(10,2))
        self._cont_var = tk.StringVar(value="Tous")
        cb_cont = ttk.Combobox(flt, textvariable=self._cont_var, width=10,
                               values=["Tous","Europe","Asie","Afrique",
                                       "Am. Nord","Am. Sud","Océanie","Antarctique"])
        cb_cont.pack(side="left", padx=2)
        cb_cont.bind("<<ComboboxSelected>>", lambda _e: self._filter())

        ttk.Label(flt, text="Bande:").pack(side="left", padx=(10,2))
        self._band_var = tk.StringVar(value="All")
        cb_band = ttk.Combobox(flt, textvariable=self._band_var, width=7,
                               values=["All","160m","80m","40m","30m","20m",
                                       "17m","15m","12m","10m","6m","2m"])
        cb_band.pack(side="left", padx=2)
        cb_band.bind("<<ComboboxSelected>>", lambda _e: self._filter())

        ttk.Label(flt, text="Afficher:").pack(side="left", padx=(10,2))
        self._show_var = tk.StringVar(value="Toutes (340)")
        cb_show = ttk.Combobox(flt, textvariable=self._show_var, width=16,
                               values=["Toutes (340)", "Travaillées",
                                       "Confirmées", "Non travaillées"])
        cb_show.pack(side="left", padx=2)
        cb_show.bind("<<ComboboxSelected>>", lambda _e: self._filter())

        ttk.Button(flt, text="✕ Effacer", command=self._clear_filter,
                   bootstyle="secondary-outline", width=9).pack(side="left", padx=6)

        # Treeview
        self.tree = ttk.Treeview(parent, columns=_COLS, show="headings",
                                 style="Custom.Treeview")
        for col, w in zip(_COLS, _COL_W):
            self.tree.heading(col, text=col,
                              command=lambda c=col: self._sort_by_col(c))
            anchor = "w" if col in ("Entité DXCC", "Bandes", "Notes") else "center"
            self.tree.column(col, width=w, anchor=anchor, stretch=(col == "Notes"))

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("confirmed", background="#1a5e20", foreground="#58d68d")
        self.tree.tag_configure("worked",    background="#11273f", foreground="#e6edf3")
        self.tree.tag_configure("unworked",  background="#0d1117", foreground="#484f58")
        self.tree.tag_configure("eu",        background="#1a2a4a", foreground="#85c1e9")
        self.tree.tag_configure("ant",       background="#2a1a0a", foreground="#aaa")

        self.tree.bind("<Double-1>", self._edit_notes)

    # ── Données ───────────────────────────────────────────────────────────────

    def refresh(self):
        """Recharge toutes les données (logbook + géo) et rafraîchit l'affichage."""
        home = self._grid_latlon("JO20SP")  # position ON5AM
        try:
            import station_master as _sm
            home = self._grid_latlon(_sm.MY_GRID)
        except Exception:
            pass

        # -- Données logbook --
        c = self.conn.cursor()
        rows_db = c.execute(
            "SELECT callsign, band, mode, qso_date, lotw_stat, eqsl_stat, qsl_rcvd "
            "FROM qsos"
        ).fetchall()

        dxcc_log = {}
        for call, band, mode, date, lotw, eqsl, qslr in rows_db:
            entity = self._get_country(call)
            if not entity:
                continue
            if entity not in dxcc_log:
                dxcc_log[entity] = {"qsos": 0, "bands": set(), "dates": [], "confirmed": False}
            d = dxcc_log[entity]
            d["qsos"] += 1
            d["bands"].add(band or "?")
            if date:
                d["dates"].append(date)
            confirmed = (
                (lotw and lotw.upper() in ("OK", "YES", "Y", "LOTW")) or
                (eqsl and eqsl.upper() in ("OK", "YES", "Y", "EQSL")) or
                (qslr and qslr.upper() in ("Y", "YES", "R"))
            )
            if confirmed:
                d["confirmed"] = True

        for row in c.execute("SELECT entity, confirmed FROM dxcc_confirmed WHERE confirmed=1"):
            if row[0] in dxcc_log:
                dxcc_log[row[0]]["confirmed"] = True

        # Notes depuis DB
        notes_db = {row[0]: row[1] for row in
                    c.execute("SELECT entity, notes FROM dxcc_confirmed WHERE notes IS NOT NULL AND notes != ''")}

        # -- Construction des lignes unifiées --
        self._rows = []
        seen = set()
        for prefix, entity, cont, lat, lon in DXCC_DATA:
            if entity in seen:
                continue
            seen.add(entity)

            dist_km = short_az = long_az = ""
            if home:
                try:
                    lat1, lon1 = map(math.radians, home)
                    lat2r = math.radians(lat); lon2r = math.radians(lon)
                    dlon = lon2r - lon1
                    cos_c = math.sin(lat1)*math.sin(lat2r) + math.cos(lat1)*math.cos(lat2r)*math.cos(dlon)
                    dist_km  = int(6371 * math.acos(max(-1.0, min(1.0, cos_c))))
                    y = math.sin(dlon) * math.cos(lat2r)
                    x = math.cos(lat1)*math.sin(lat2r) - math.sin(lat1)*math.cos(lat2r)*math.cos(dlon)
                    short_az = int((math.degrees(math.atan2(y, x)) + 360) % 360)
                    long_az  = int((short_az + 180) % 360)
                except Exception:
                    pass

            cont_name = CONTINENT_NAMES.get(cont, cont)
            log = dxcc_log.get(entity)
            if log:
                qsos      = log["qsos"]
                bands     = ", ".join(sorted(log["bands"]))
                first_date = min(log["dates"]) if log["dates"] else ""
                if log["confirmed"]:
                    statut = "✅ Confirmé"
                else:
                    statut = "📡 Travaillé"
            else:
                qsos = first_date = bands = ""
                statut = "—"

            self._rows.append({
                "prefix": prefix, "entity": entity, "cont": cont_name,
                "cont_code": cont,
                "lat": f"{lat:.1f}", "lon": f"{lon:.1f}",
                "dist": dist_km, "short": short_az, "long": long_az,
                "qsos": qsos, "bands": bands, "first_date": first_date,
                "statut": statut, "notes": notes_db.get(entity, ""),
            })

        self._filter()

    # ── Filtre / Tri / Affichage ──────────────────────────────────────────────

    def _filter(self):
        search  = self._search_var.get().strip().lower()
        cont_f  = self._cont_var.get()
        band_f  = self._band_var.get().lower()
        show_f  = self._show_var.get()

        filtered = []
        for row in self._rows:
            if cont_f != "Tous" and row["cont"] != cont_f:
                continue
            if show_f == "Travaillées"    and row["statut"] == "—":
                continue
            if show_f == "Confirmées"     and row["statut"] != "✅ Confirmé":
                continue
            if show_f == "Non travaillées" and row["statut"] != "—":
                continue
            if band_f != "all" and row["qsos"] and band_f not in row["bands"].lower():
                continue
            if search and search not in row["prefix"].lower() and search not in row["entity"].lower():
                continue
            filtered.append(row)

        # Tri
        key = self._sort_col_key
        if key in ("dist", "short", "long", "qsos"):
            filtered.sort(key=lambda r: (r[key] if r[key] != "" else 999999),
                          reverse=self._sort_rev)
        else:
            filtered.sort(key=lambda r: r[key], reverse=self._sort_rev)

        self._display(filtered)

    def _display(self, rows):
        for item in self.tree.get_children():
            self.tree.delete(item)

        worked = confirmed = 0
        for row in rows:
            dist_s  = f"{row['dist']:,}" if row["dist"] != "" else "?"
            short_s = f"{row['short']}°" if row["short"] != "" else "?"
            long_s  = f"{row['long']}°"  if row["long"]  != "" else "?"

            if row["statut"] == "✅ Confirmé":
                tag = "confirmed"; confirmed += 1; worked += 1
            elif row["statut"] == "📡 Travaillé":
                tag = "worked"; worked += 1
            elif row["cont_code"] == "EU":
                tag = "eu"
            elif row["cont_code"] == "AN":
                tag = "ant"
            else:
                tag = "unworked"

            self.tree.insert("", "end", values=(
                row["prefix"], row["entity"], row["cont"],
                dist_s, short_s, long_s,
                row["qsos"] or "", row["bands"], row["first_date"],
                row["statut"], row["notes"],
            ), tags=(tag,))

        total = len(rows)
        self._info_var.set(
            f"{total} entités  |  {worked} travaillées  |  {confirmed} confirmées"
        )

    def _sort_by_col(self, col):
        key = _COL_KEY.get(col, "entity")
        if self._sort_col_key == key:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col_key = key
            self._sort_rev = False
        self._filter()

    def _clear_filter(self):
        self._search_var.set("")
        self._cont_var.set("Tous")
        self._band_var.set("All")
        self._show_var.set("Toutes (340)")
        self._filter()

    # ── Actions DXCC ─────────────────────────────────────────────────────────

    def confirm_selection(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Sélectionnez d'abord des entités.")
            return
        c = self.conn.cursor()
        for item in sel:
            entity = self.tree.item(item)["values"][1]
            c.execute(
                "INSERT OR REPLACE INTO dxcc_confirmed (entity, confirmed) VALUES (?,1)",
                (entity,)
            )
        self.conn.commit()
        self.refresh()
        try:
            self.app.status_var.set(f"✅ {len(sel)} entité(s) confirmée(s)")
        except Exception:
            pass

    def unconfirm_selection(self):
        sel = self.tree.selection()
        if not sel:
            return
        c = self.conn.cursor()
        for item in sel:
            entity = self.tree.item(item)["values"][1]
            c.execute("UPDATE dxcc_confirmed SET confirmed=0 WHERE entity=?", (entity,))
        self.conn.commit()
        self.refresh()

    def _edit_notes(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals   = self.tree.item(sel[0])["values"]
        entity = vals[1]
        notes  = vals[10] if len(vals) > 10 else ""

        win = tk.Toplevel(self.root)
        win.title(f"📝 Notes DXCC — {entity}")
        win.geometry("420x200")
        win.grab_set()
        frm = ttk.Frame(win, padding=15); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Entité : {entity}", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(frm, text="Notes :").pack(anchor="w")
        txt = tk.Text(frm, height=4, font=("Arial", 10))
        txt.pack(fill="both", expand=True, pady=4)
        txt.insert("1.0", notes)

        def _save():
            new_notes = txt.get("1.0", tk.END).strip()
            c = self.conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO dxcc_confirmed (entity, notes, confirmed) "
                "VALUES (?, ?, COALESCE((SELECT confirmed FROM dxcc_confirmed WHERE entity=?), 0))",
                (entity, new_notes, entity)
            )
            self.conn.commit()
            win.destroy()
            self.refresh()

        bf = ttk.Frame(win); bf.pack(fill="x", padx=15, pady=5)
        ttk.Button(bf, text="💾 OK",   command=_save,       bootstyle="success").pack(side="left")
        ttk.Button(bf, text="✖ Annuler", command=win.destroy, bootstyle="secondary").pack(side="right")
