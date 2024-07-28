# Project started on 28 june 2024 by Samarth Pai
import art,termcolor,random,sys,time,threading,string
import bencoding as ben
import requests
from pynput.keyboard import Key,Controller

dbServerUrl = "https://hangman-server.glitch.me"
strangerPlayerNo = {1:2,2:1}.get
keyboard = Controller()
systummHanged = False
matchDone = False

def wakeUp():
    requests.get(dbServerUrl)

def interruptKeyboard():
    keyboard.press(Key.enter)
    keyboard.release(Key.enter)
    
def fetchWord():
    with open("wordBank.ben","rb") as f:
        wordBank = ben.bdecode(f.read())
    return random.choice(wordBank).decode()

def generateRoomID():
    chars = string.ascii_letters
    return "".join(random.choice(chars) for i in range(6))

def updateTiming(roomID,json: dict):
    requests.put(f"{dbServerUrl}/updateTiming/{roomID}",json=json)

def getTiming(roomID,playerNo):
    return requests.get(f"{dbServerUrl}/getTiming/{roomID}/{playerNo}").json()

def isOpponentOnline(roomID,playerNo):
    return time.time()-getTiming(roomID,strangerPlayerNo(playerNo))<25

def matchAnimation(text,endText,condition,roomID):
    animation = [f"{text} .", f"{text} ..", f"{text} ..."]
    while True:
        for frame in animation:
            sys.stdout.write("\r" + frame + "   ")
            sys.stdout.flush()
            if condition(roomID):
                print('\n'*bool(endText)+endText)
                return

def getWord(roomID):
    return requests.get(f"{dbServerUrl}/getWord/{roomID}").json()

def wait(roomID):
    matchStatus =  requests.get(f"{dbServerUrl}/matchStatus/{roomID}").json()
    return matchStatus

def getSubmittedAlpha(roomID):
    return requests.get(f"{dbServerUrl}/getSubmittedAlpha/{roomID}").json()

def hasSubmittedAlpha(roomID):  
    return bool(getSubmittedAlpha(roomID)) or systummHanged

def flushAlpha(roomID):
    requests.put(f"{dbServerUrl}/flushAlpha/{roomID}")

def isPlaying(roomID):
    return requests.get(f"{dbServerUrl}/isPlaying/{roomID}").json()

def declareFinished(roomID):
    requests.put(f"{dbServerUrl}/declareFinish/{roomID}")


def completeWithStranger():
    global matchFound
    matchSearch = requests.get(f"{dbServerUrl}/findMatchRoom/completeWithStranger").json()
    if matchSearch:
        # requests.get(f"{dbServerUrl}/getWord/{roomID}").json()
        wordToBePredicted = fetchWord().lower()
        wordLen = len(wordToBePredicted)
        guessStartIndices = random.sample(range(wordLen),2)

        playRoomDict = {
            "mode":"completeWithStranger",
            "roomID":matchSearch,
            "word":wordToBePredicted,
            "guessedIndices":guessStartIndices,
            "player1Time":time.time(),
            "player2Time":time.time(),
            "player1Turn": True,
            "finishedPlaying":False,
            "submittedAlpha":"",
        }
        requests.post(f"{dbServerUrl}/shiftToPlay/{matchSearch}",json=playRoomDict)
        requests.put(f"{dbServerUrl}/declareMatch/{matchSearch}")
        playCompleteWithStranger(matchSearch,2)
        declareFinished(matchSearch)

    else:
        roomID = generateRoomID()
        requests.post(f"{dbServerUrl}/createMatchRoom",
                      json = {"mode":"completeWithStranger",
                              "roomID":roomID,
                              "matchFound":False
                              })
        matchAnimation("Finding match","Match found!",wait,roomID)
        playCompleteWithStranger(roomID,1)

def timeManager(roomID,playerNo):
    global systummHanged, matchDone
    while isOpponentOnline(roomID,playerNo) and isPlaying(roomID):
        timingDict ={
            "timing":time.time(),
            "playerNo": playerNo
        }
        updateTiming(roomID,json=timingDict)
        if matchDone==True:
            return
    if isPlaying(roomID):
        print(termcolor.colored("\nThe stranger has left the game :-(","red",attrs=["bold"]))
        playerTurn = int(player1Turn(roomID)) or 2
        if playerNo == playerTurn:
            interruptKeyboard()
        systummHanged = True

def playCompleteWithStranger(roomID,playerNo):
    global systummHanged, matchDone
    
    print("I am player",playerNo)
    timeoutThread = threading.Thread(target=timeManager,args=[roomID,playerNo],daemon=True)
    timeoutThread.start()

    attempts = 5
    wordToBePredicted = requests.get(f"{dbServerUrl}/getWord/{roomID}").json()
    wordMatches = list(wordToBePredicted)
    guessedIndices = [False]*len(wordToBePredicted)

    guessStartIndices = requests.get(f"{dbServerUrl}/getGuessedIndices/{roomID}").json()
    for i in guessStartIndices:
        wordMatches[i] = "_"
        guessedIndices[i] = True

    print(termcolor.colored("You are player no. ","white",attrs=["bold"]),termcolor.colored(str(playerNo),"yellow",attrs=["bold"]))
    while attempts:
        displayString = termcolor.colored(" ".join(["_",c][g] for c,g in zip(wordToBePredicted,guessedIndices)),"yellow",attrs = ["bold"])
        print(f"\n{displayString}")
        if player1Turn(roomID):
            if playerNo==1:
                print(termcolor.colored("Your turn !","light_yellow",attrs=["bold"]))
                guess = input(termcolor.colored("Input a char to guess: ","white",attrs = ["bold"])).lower()
                if systummHanged:
                    systummHanged = False
                    return
                try:
                    if not guess:
                        print(termcolor.colored("Please enter at least one character to guess a letter","red",attrs=["bold"]))
                        continue
                    i =  wordMatches.index(guess)
                    wordMatches[i] = "_"
                    guessedIndices[i] = True

                    print(termcolor.colored("Correct!","green",attrs=["bold"]))
                except Exception as e:
                    attempts-=1
                    print(termcolor.colored("Wrong. Attempts left: "+str(attempts),"red",attrs=["bold"]))
                submitAlpha(roomID,guess[0])
                turnPlayer(roomID)
                print()
            else:
                matchAnimation("Waiting for stranger input","",hasSubmittedAlpha,roomID)
                if systummHanged:
                    systummHanged = False
                    return
                guess = getSubmittedAlpha(roomID)
                try:
                    i =  wordMatches.index(guess)

                    wordMatches[i] = "_"
                    guessedIndices[i] = True

                    print(termcolor.colored("Correct!","green",attrs=["bold"]))
                except Exception as e:
                    attempts-=1
                    print(termcolor.colored("Wrong. Attempts left: "+str(attempts),"red",attrs=["bold"]))
                print()
                flushAlpha(roomID)
        else:
            if playerNo==1:
                matchAnimation("Waiting for stranger input","",hasSubmittedAlpha,roomID)
                if systummHanged:
                    systummHanged = False
                    return
                guess = getSubmittedAlpha(roomID)
                try:
                    i =  wordMatches.index(guess)

                    wordMatches[i] = "_"
                    guessedIndices[i] = True

                    print(termcolor.colored("Correct!","green",attrs=["bold"]))
                except Exception as e:
                    attempts-=1
                    print(termcolor.colored("Wrong. Attempts left: "+str(attempts),"red",attrs=["bold"]))
                print()
                flushAlpha(roomID)
            else:
                print(termcolor.colored("Your turn !","light_yellow",attrs=["bold"]))
                guess = input(termcolor.colored("Input a char to guess: ","white",attrs = ["bold"])).lower()
                if systummHanged:
                    systummHanged = False
                    return
                try:
                    if not guess:
                        print(termcolor.colored("Please enter at least one character to guess a letter","red",attrs=["bold"]))
                        continue
                    i =  wordMatches.index(guess)
                    wordMatches[i] = "_"
                    guessedIndices[i] = True

                    print(termcolor.colored("Correct!","green",attrs=["bold"]))
                except Exception as e:
                    attempts-=1
                    print(termcolor.colored("Wrong. Attempts left: "+str(attempts),"red",attrs=["bold"]))
                submitAlpha(roomID,guess[0])
                turnPlayer(roomID)
                print()

        if all(guessedIndices):
            break
    if attempts:
        print(termcolor.colored(wordToBePredicted,"yellow",attrs=["bold"]))
        print(art.text2art("W!","random"))
    else:
        print(f"Correct word: {termcolor.colored(wordToBePredicted,"yellow",attrs=["bold"])}")
        print("Try better next time ;-)")
        print()

    matchDone = True


def player1Turn(roomID):
    return requests.get(f"{dbServerUrl}/playerOneTurn/{roomID}").json()

def turnPlayer(roomID):
    requests.put(f"{dbServerUrl}/turnPlayer/{roomID}")

def submitAlpha(roomID,alpha):
    requests.post(f"{dbServerUrl}/submitAlpha/{roomID}/{alpha}")

def main():
    wakeUp()
    print(termcolor.colored(art.text2art("HANGMAN","jetbrains"),"light_blue",attrs=["bold"]))
    modes = {
        1:"Single player",
        2:"Multiplayer"
    }
    multiplayerModes = {
        1:"Complete with stranger"
    }
    while True:
        for code,mode in modes.items():
            print(f"Enter {termcolor.colored(code,"green",attrs=["bold"])} for {termcolor.colored(mode,"green",attrs=["bold"])} mode")
        print(f"Enter {termcolor.colored(3,"green",attrs=["bold"])} to exit")
        modeInput = int(input(termcolor.colored("Enter: ","white",attrs=["bold"])))
        match modeInput:
            case 1:
                singlePlayer()
            case 2:
                while True:
                    for code,mode in multiplayerModes.items():
                        print(f"Enter {termcolor.colored(code,"green",attrs=["bold"])} for {termcolor.colored(mode,"green",attrs=["bold"])} mode")
                    print(f"Enter {termcolor.colored(2,"green",attrs=["bold"])} to go back")
                    multiplayerModeInput = int(input(termcolor.colored("Enter: ","white",attrs=["bold"])))
                    match multiplayerModeInput:
                        case 1:
                            completeWithStranger()
                        case 2:
                            break
                        case 3:
                            print(termcolor.colored("Invalid input. Try again","red",attrs=["bold"]))
            case 3:
                print()
                print(termcolor.colored("Thanks for using. Made by Samarth Pai aka chou ;-)","light_yellow",attrs=["bold"]))
                exit(0)
            case 4:
                print(termcolor.colored("Invalid input. Try again","red",attrs=["bold"]))


def singlePlayer():
    wordToBePredicted = fetchWord().lower()
    wordMatches = list(wordToBePredicted)

    wordLen = len(wordToBePredicted)
    guessedIndices = [False]*wordLen

    guessStartIndices = random.sample(range(wordLen),2)
    for i in guessStartIndices:
        wordMatches[i] = "_"
        guessedIndices[i] = True
    attempts = 5


    while attempts:
        displayString = termcolor.colored(" ".join(["_",c][g] for c,g in zip(wordToBePredicted,guessedIndices)),"yellow",attrs = ["bold"])
        print(f"\n{displayString}")

        guess = input(termcolor.colored("Input a char to guess: ","white",attrs = ["bold"])).lower()
        try:
            if not guess:
                print(termcolor.colored("Please enter at least one character to guess a letter","red",attrs=["bold"]))
                continue
            i =  wordMatches.index(guess)
            
            wordMatches[i] = "_"
            guessedIndices[i] = True

            print(termcolor.colored("Correct!","green",attrs=["bold"]))
        except Exception as e:
            attempts-=1
            print(termcolor.colored("Wrong. Attempts left: "+str(attempts),"red",attrs=["bold"]))
        
        if all(guessedIndices):
            break
        

    if attempts:
        print(termcolor.colored(wordToBePredicted,"yellow",attrs=["bold"]))
        print(art.text2art("W!","random"))
    else:
        print(f"Correct word: {termcolor.colored(wordToBePredicted,"yellow",attrs=["bold"])}")
        print("Try better next time ;-)")
        print()

if __name__=="__main__":
    main()