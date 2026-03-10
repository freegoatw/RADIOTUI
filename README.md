![PX7 Terminal Radio](https://github.com/user-attachments/assets/d2737200-ebd8-4736-b460-c9af140e8137)

# PX7 Terminal Radio

PX7 Terminal Radio is a lightweight **command-line internet radio player** written in Python. It allows you to **search, stream, and control thousands of online radio stations directly from your terminal.** Stations are fetched using the **Radio Browser API**, and playback is handled through **VLC**.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Common Commands](#common-commands)
- [API Used](#api-used)
- [License](#license)


## Features

- Search internet radio stations  
- Stream radio directly from the terminal  
- Filter and sort stations using API options  
- Control playback (play, pause, resume, stop)  
- Lightweight command-line interface

---
## Requirements

- Python 3.9+
- VLC Media Player

## Installation

#### 1. Clone the repository:
If you just want to use:
```
git clone --depth 1 https://github.com/px7nn/px7-radio.git
cd px7-radio
```
else:
```
git clone https://github.com/px7nn/px7-radio.git
cd px7-radio
```
#### 2. Install Python dependencies
```
pip install -r requirements.txt
```
#### 3. Run the application
```
python main.py
```
After starting, you will see the terminal prompt:
```
>>
```
You can now search and play radio stations.
Example:
```
>> radio search lofi
>> play 1
```

#### Usage

![Screenshot](https://github.com/user-attachments/assets/eb1b5da1-c710-4570-973d-9e59179c7072)

#### Common Commands

| Command                                 | Description                                     |
|----------------------------------------|-----------------------------------------------|
| `radio search <query>`                  | Search radio stations by name                 |
| `radio search --tag=<tag>`              | Search stations by tag (e.g., jazz, lofi)     |
| `radio search --country=<country>`      | Filter stations by country                    |
| `radio search --language=<language>`    | Filter stations by language                   |
| `radio search --limit=<number> <query>` | Limit the number of results                   |
| `radio search --order=votes`            | Sort results (e.g., clickcount, votes, bitrate) |
| `play <index>`                          | Play a station from the search results        |
| `pause`                                 | Pause playback                                |
| `resume`                                | Resume playback                               |
| `stop`                                  | Stop playback                                 |
| `clear`                                 | Clear terminal output                         |
| `exit`                                  | Exit the program                              |

Additional filters and parameters are supported since PX7 Terminal Radio is compatible with the **Radio Browser API**.

You can pass API parameters using the format:
`--parameter=value`

Example:
```
>> radio search lofi --limit=5
>> radio search --tag=jazz --country=US
>> radio search chill --order=clickcount
```
For the complete list of supported parameters, see the Radio Browser API documentation:  
https://www.radio-browser.info/

## API Used
This project uses the public Radio Browser API:  
https://www.radio-browser.info/

## License

This project is licensed under the MIT License.  
See the [LICENSE](LICENSE) file for details.
