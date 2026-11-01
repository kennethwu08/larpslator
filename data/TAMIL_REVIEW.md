# Tamil terminology and reference review

Status: DRAFT. These translations are assistant-authored candidates, not verified academic extractions.
A Tamil-speaking teammate must check natural usage, sporting sense, and every reference translation.
Prefer natural loanwords where that is how Tamil-speaking programmers or players actually talk.

## How to record a review

1. Edit preferred_ta and definition_ta in data/glossaries/tamil-drafts.jsonl as needed.
2. Keep the matching data/glossaries/selected/<domain>-ta.json value synchronized.
3. After real review, set human_review.status to approved and human_review.reviewer to the actual reviewer's name in each accepted term record.
4. Check both examples per term in data/eval-ta.jsonl; edit reference_ta, expected_terms_ta, and match_fragments_ta. Set reference_status and human_review.status to approved only after review, and fill reviewer.
5. Match fragments are substring/stem hints, not approved full-word translations. Valid Tamil inflections can defeat exact matching.
6. Never mark an API result correct just because it contains the glossary word.

## cs

| English | Draft Tamil | Draft meaning |
|---|---|---|
| process | செயல்முறை | இயக்கத்தில் உள்ள ஒரு நிரலின் நிகழ்வு. |
| thread | இழை | ஒரு செயல்முறைக்குள் இயங்கும் செயலாக்கப் பாதை. |
| memory | நினைவகம் | தரவு மற்றும் நிரல் கட்டளைகளைச் சேமிக்கும் வளம். |
| server | சேவையகம் | பிற நிரல்களுக்கு சேவை வழங்கும் கணினி அல்லது நிரல். |
| port | துறைமுக எண் | வலையமைப்பில் சேவையை அடையாளப்படுத்தும் எண். |
| socket | சாக்கெட் | வலையமைப்புத் தொடர்பின் முனைப்புள்ளி. |
| argument | செயலுருபு | செயற்கூறை அழைக்கும்போது கொடுக்கப்படும் மதிப்பு. |
| return | திருப்பி அனுப்பு | அழைத்த நிரலுக்கு முடிவு மதிப்பை வழங்குதல். |
| class | வகுப்பு | பொருட்களின் பண்புகளையும் செயல்களையும் வரையறுக்கும் அமைப்பு. |
| object | பொருள் | பண்புகளும் செயல்களும் கொண்ட நிரலாக்க நிகழ்வு. |
| key | திறவுகோல் | அகராதியில் மதிப்பை அடையாளப்படுத்தும் உருப்படி. |
| value | மதிப்பு | ஒரு மாறி அல்லது தரவு உருப்படியில் உள்ள தரவு. |
| stack | அடுக்கு | கடைசியில் சேர்த்ததை முதலில் எடுக்கும் தரவமைப்பு. |
| queue | வரிசை | முதலில் சேர்ந்ததை முதலில் செயலாக்கும் தரவமைப்பு. |
| cache | இடைநினைவகம் | மீண்டும் தேவைப்படும் தரவை விரைவாகப் பெறும் சேமிப்பு. |

### Held-out draft references

**ta-cs-01-1 — process**
- English: The process is using too much memory.
- Draft Tamil: இந்தச் செயல்முறை அதிக நினைவகத்தைப் பயன்படுத்துகிறது.

**ta-cs-01-2 — process**
- English: Stop the process before restarting the server.
- Draft Tamil: சேவையகத்தை மீண்டும் தொடங்குவதற்கு முன் செயல்முறையை நிறுத்துங்கள்.

**ta-cs-02-1 — thread**
- English: This thread handles incoming requests.
- Draft Tamil: இந்த இழை உள்வரும் கோரிக்கைகளைக் கையாளுகிறது.

**ta-cs-02-2 — thread**
- English: Two threads are updating the same variable.
- Draft Tamil: இரண்டு இழைகள் ஒரே மாறியைப் புதுப்பிக்கின்றன.

**ta-cs-03-1 — memory**
- English: Free the memory after processing the image.
- Draft Tamil: படத்தைச் செயலாக்கிய பின் நினைவகத்தை விடுவியுங்கள்.

**ta-cs-03-2 — memory**
- English: The application ran out of memory.
- Draft Tamil: பயன்பாட்டிற்குப் போதுமான நினைவகம் இல்லை.

**ta-cs-04-1 — server**
- English: The server rejected the request.
- Draft Tamil: சேவையகம் கோரிக்கையை நிராகரித்தது.

**ta-cs-04-2 — server**
- English: Restart the server after changing the configuration.
- Draft Tamil: அமைப்பை மாற்றிய பின் சேவையகத்தை மீண்டும் தொடங்குங்கள்.

**ta-cs-05-1 — port**
- English: The application listens on port 8000.
- Draft Tamil: பயன்பாடு துறைமுக எண் 8000-இல் கோரிக்கைகளுக்காகக் காத்திருக்கிறது.

**ta-cs-05-2 — port**
- English: Another program is already using this port.
- Draft Tamil: வேறொரு நிரல் ஏற்கெனவே இந்தத் துறைமுக எண்ணைப் பயன்படுத்துகிறது.

**ta-cs-06-1 — socket**
- English: Close the socket when the client disconnects.
- Draft Tamil: கிளையன்ட் துண்டிக்கப்படும்போது சாக்கெட்டை மூடுங்கள்.

**ta-cs-06-2 — socket**
- English: The socket receives audio from the badge.
- Draft Tamil: சாக்கெட் பேட்ஜிலிருந்து ஒலியைப் பெறுகிறது.

**ta-cs-07-1 — argument**
- English: Pass the filename as the first argument.
- Draft Tamil: கோப்புப் பெயரை முதல் செயலுருபாக அனுப்புங்கள்.

**ta-cs-07-2 — argument**
- English: The function expects two arguments.
- Draft Tamil: இந்தச் செயற்கூறு இரண்டு செயலுருபுகளை எதிர்பார்க்கிறது.

**ta-cs-08-1 — return**
- English: Return an empty list if no records are found.
- Draft Tamil: பதிவுகள் கிடைக்காவிட்டால் காலிப் பட்டியலைத் திருப்பி அனுப்புங்கள்.

**ta-cs-08-2 — return**
- English: The function returns the translated text.
- Draft Tamil: செயற்கூறு மொழிபெயர்க்கப்பட்ட உரையைத் திருப்பி அனுப்புகிறது.

**ta-cs-09-1 — class**
- English: Create a class for the translation settings.
- Draft Tamil: மொழிபெயர்ப்பு அமைப்புகளுக்காக ஒரு வகுப்பை உருவாக்குங்கள்.

**ta-cs-09-2 — class**
- English: This class contains the audio configuration.
- Draft Tamil: இந்த வகுப்பில் ஒலி அமைப்புத் தகவல்கள் உள்ளன.

**ta-cs-10-1 — object**
- English: Convert the object to JSON.
- Draft Tamil: பொருளை JSON வடிவத்திற்கு மாற்றுங்கள்.

**ta-cs-10-2 — object**
- English: The object stores the current language.
- Draft Tamil: இந்தப் பொருள் தற்போதைய மொழியைச் சேமிக்கிறது.

**ta-cs-11-1 — key**
- English: Use the term as the dictionary key.
- Draft Tamil: சொல்லை அகராதியின் திறவுகோலாகப் பயன்படுத்துங்கள்.

**ta-cs-11-2 — key**
- English: Check whether the key exists before reading its value.
- Draft Tamil: மதிப்பைப் படிப்பதற்கு முன் திறவுகோல் உள்ளதா என்று பாருங்கள்.

**ta-cs-12-1 — value**
- English: Update the value when the button is pressed.
- Draft Tamil: பொத்தானை அழுத்தும்போது மதிப்பைப் புதுப்பியுங்கள்.

**ta-cs-12-2 — value**
- English: The value must be a string.
- Draft Tamil: மதிப்பு ஒரு சரமாக இருக்க வேண்டும்.

**ta-cs-13-1 — stack**
- English: Push the new item onto the stack.
- Draft Tamil: புதிய உருப்படியை அடுக்கில் சேருங்கள்.

**ta-cs-13-2 — stack**
- English: Remove the top item from the stack.
- Draft Tamil: அடுக்கின் மேலுள்ள உருப்படியை அகற்றுங்கள்.

**ta-cs-14-1 — queue**
- English: Put the request in the queue.
- Draft Tamil: கோரிக்கையை வரிசையில் சேருங்கள்.

**ta-cs-14-2 — queue**
- English: The queue contains three audio clips.
- Draft Tamil: வரிசையில் மூன்று ஒலித் துண்டுகள் உள்ளன.

**ta-cs-15-1 — cache**
- English: Store the translated audio in the cache.
- Draft Tamil: மொழிபெயர்க்கப்பட்ட ஒலியை இடைநினைவகத்தில் சேமியுங்கள்.

**ta-cs-15-2 — cache**
- English: Clear the cache after updating the glossary.
- Draft Tamil: சொற்களஞ்சியத்தைப் புதுப்பித்த பின் இடைநினைவகத்தை அழியுங்கள்.

## tennis

| English | Draft Tamil | Draft meaning |
|---|---|---|
| serve | சர்வ் | புள்ளிக்கான ஆட்டத்தைத் தொடங்கும் அடிப்பு. |
| love | லவ் | டென்னிஸ் புள்ளிக் கணக்கில் பூஜ்ஜியம். |
| break point | பிரேக் பாயிண்ட் | ரிசீவர் அடுத்த புள்ளியை வென்றால் கேமை வெல்லும் நிலை. |
| break | சர்வீஸ் கேமை வெல் | எதிராளி சர்வ் செய்யும் கேமை வெல்லுதல். |
| set | செட் | பல கேம்களால் ஆன போட்டிப் பகுதி. |
| match | போட்டி | ஒன்று அல்லது பல செட்களால் முடிவு செய்யப்படும் முழு ஆட்டம். |
| deuce | டியூஸ் | வழக்கமான கேமில் நாற்பது-நாற்பது சமநிலை. |
| advantage | அட்வான்டேஜ் | டியூஸுக்குப் பிறகு ஒரு புள்ளி முன்னிலை. |
| let | லெட் | குறிப்பிட்ட சர்வ் அல்லது புள்ளியை மீண்டும் ஆடும் தீர்ப்பு. |
| ace | ஏஸ் | எதிராளி தொட முடியாத சரியான சர்வால் கிடைக்கும் புள்ளி. |
| fault | ஃபால்ட் | சரியாக அமையாத சர்வ். |
| double fault | டபுள் ஃபால்ட் | இரண்டு சர்வ் முயற்சிகளும் தவறி புள்ளியை இழத்தல். |
| volley | வாலி | பந்து தரையில் துள்ளுவதற்கு முன் அடித்தல். |
| slice | ஸ்லைஸ் | பின்சுழற்சி அல்லது பக்கச்சுழற்சி கொடுத்து அடிக்கும் முறை. |
| lob | லாப் | எதிராளியின் தலைக்கு மேல் உயரமாகச் செல்லும் அடிப்பு. |

### Held-out draft references

**ta-tennis-01-1 — serve**
- English: Her first serve landed outside the service box.
- Draft Tamil: அவரது முதல் சர்வ் சர்வீஸ் பெட்டிக்கு வெளியே விழுந்தது.

**ta-tennis-01-2 — serve**
- English: Aim your serve toward the receiver's backhand.
- Draft Tamil: உங்கள் சர்வை எதிராளியின் பேக்ஹேண்ட் பக்கமாகச் செலுத்துங்கள்.

**ta-tennis-02-1 — love**
- English: The score is fifteen-love.
- Draft Tamil: புள்ளிக் கணக்கு பதினைந்து-லவ்.

**ta-tennis-02-2 — love**
- English: He leads forty-love in this game.
- Draft Tamil: இந்த கேமில் அவர் நாற்பது-லவ் என முன்னிலையில் உள்ளார்.

**ta-tennis-03-1 — break point**
- English: She saved a break point with an ace.
- Draft Tamil: அவர் ஒரு ஏஸ் மூலம் பிரேக் பாயிண்டைக் காப்பாற்றினார்.

**ta-tennis-03-2 — break point**
- English: The receiver has two break points.
- Draft Tamil: ரிசீவருக்கு இரண்டு பிரேக் பாயிண்ட்கள் உள்ளன.

**ta-tennis-04-1 — break**
- English: She needs to break in the next game.
- Draft Tamil: அடுத்த கேமில் அவர் எதிராளியின் சர்வீஸ் கேமை வெல்ல வேண்டும்.

**ta-tennis-04-2 — break**
- English: He managed to break after a long rally.
- Draft Tamil: நீண்ட ராலிக்குப் பிறகு அவர் எதிராளியின் சர்வீஸ் கேமை வென்றார்.

**ta-tennis-05-1 — set**
- English: She won the first set six-four.
- Draft Tamil: அவர் முதல் செட்டை ஆறு-நான்கு என வென்றார்.

**ta-tennis-05-2 — set**
- English: The second set went to a tiebreak.
- Draft Tamil: இரண்டாவது செட் டைபிரேக்கிற்குச் சென்றது.

**ta-tennis-06-1 — match**
- English: This match will be decided in the final set.
- Draft Tamil: இந்தப் போட்டியின் முடிவு இறுதி செட்டில் தீர்மானிக்கப்படும்.

**ta-tennis-06-2 — match**
- English: She won the match in straight sets.
- Draft Tamil: அவர் நேர்செட்களில் போட்டியை வென்றார்.

**ta-tennis-07-1 — deuce**
- English: The game is back at deuce.
- Draft Tamil: கேம் மீண்டும் டியூஸ் நிலைக்கு வந்துள்ளது.

**ta-tennis-07-2 — deuce**
- English: At deuce, the next point gives the winner advantage.
- Draft Tamil: டியூஸ் நிலையில் அடுத்த புள்ளியை வெல்பவருக்கு அட்வான்டேஜ் கிடைக்கும்.

**ta-tennis-08-1 — advantage**
- English: The server has advantage.
- Draft Tamil: சர்வ் செய்பவருக்கு அட்வான்டேஜ் உள்ளது.

**ta-tennis-08-2 — advantage**
- English: She lost the point after gaining advantage.
- Draft Tamil: அட்வான்டேஜ் பெற்ற பிறகு அவர் அடுத்த புள்ளியை இழந்தார்.

**ta-tennis-09-1 — let**
- English: The umpire called a let on the second serve.
- Draft Tamil: நடுவர் இரண்டாவது சர்வில் லெட் என்று அறிவித்தார்.

**ta-tennis-09-2 — let**
- English: A service let does not erase the previous fault.
- Draft Tamil: சர்வீஸ் லெட் முந்தைய ஃபால்ட்டை நீக்காது.

**ta-tennis-10-1 — ace**
- English: She hit an ace down the middle.
- Draft Tamil: அவர் நடுப்பகுதியில் ஒரு ஏஸ் அடித்தார்.

**ta-tennis-10-2 — ace**
- English: That ace brought the score to thirty-love.
- Draft Tamil: அந்த ஏஸ் புள்ளிக் கணக்கை முப்பது-லவ் என மாற்றியது.

**ta-tennis-11-1 — fault**
- English: The first serve was a fault.
- Draft Tamil: முதல் சர்வ் ஃபால்ட் ஆனது.

**ta-tennis-11-2 — fault**
- English: A foot fault was called during the serve.
- Draft Tamil: சர்வ் செய்யும்போது ஃபுட் ஃபால்ட் அறிவிக்கப்பட்டது.

**ta-tennis-12-1 — double fault**
- English: A double fault gave the receiver the point.
- Draft Tamil: டபுள் ஃபால்ட் காரணமாக ரிசீவருக்குப் புள்ளி கிடைத்தது.

**ta-tennis-12-2 — double fault**
- English: She avoided a double fault with a safe second serve.
- Draft Tamil: பாதுகாப்பான இரண்டாவது சர்வால் அவர் டபுள் ஃபால்ட்டைத் தவிர்த்தார்.

**ta-tennis-13-1 — volley**
- English: Meet the ball early for a firm volley.
- Draft Tamil: உறுதியான வாலிக்காகப் பந்தை முன்கூட்டியே சந்தியுங்கள்.

**ta-tennis-13-2 — volley**
- English: He finished the point with a backhand volley.
- Draft Tamil: அவர் பேக்ஹேண்ட் வாலியால் அந்தப் புள்ளியை வென்றார்.

**ta-tennis-14-1 — slice**
- English: Use a slice to keep the ball low.
- Draft Tamil: பந்தைத் தாழ்வாக வைத்திருக்க ஸ்லைஸ் பயன்படுத்துங்கள்.

**ta-tennis-14-2 — slice**
- English: Her slice serve pulled the receiver wide.
- Draft Tamil: அவரது ஸ்லைஸ் சர்வ் ரிசீவரை வெளியோரமாக நகர வைத்தது.

**ta-tennis-15-1 — lob**
- English: Send a lob over the player at the net.
- Draft Tamil: வலை அருகிலுள்ள வீரரின் தலைக்கு மேல் லாப் அடியுங்கள்.

**ta-tennis-15-2 — lob**
- English: The lob landed just inside the baseline.
- Draft Tamil: லாப் பேஸ்லைனுக்குச் சற்று உள்ளே விழுந்தது.

## pickleball

| English | Draft Tamil | Draft meaning |
|---|---|---|
| kitchen | கிச்சன் | வலை அருகிலுள்ள வாலி தடைப் பகுதியின் வழக்குப் பெயர். |
| non-volley zone | வாலி தடைப் பகுதி | வாலி அடிப்பதற்குக் கட்டுப்பாடு உள்ள வலை அருகிலான பகுதி. |
| dink | டிங்க் | எதிராளியின் கிச்சனுக்குள் மெதுவாக விழும் குறுகிய அடிப்பு. |
| third shot drop | மூன்றாவது அடிப்பு டிராப் | சர்வ், ரிட்டர்னுக்குப் பிறகு வரும் ராலியின் மூன்றாவது அடிப்பை மெதுவாகக் கிச்சனில் விடுதல். |
| drive | டிரைவ் | வேகமாகவும் தாழ்வாகவும் செல்லும் தாக்குதல் அடிப்பு. |
| paddle | பேடில் | பிக்கிள்பாலில் பயன்படுத்தும் தட்டையான பந்தடிக்கும் கருவி. |
| side out | சைட் அவுட் | சர்வ் உரிமை எதிரணிக்குச் செல்லுதல். |
| stacking | ஸ்டாக்கிங் | விருப்பமான பக்க நிலையைத் தக்கவைக்க இரட்டையர் பயன்படுத்தும் அமைப்பு. |
| reset | ரீசெட் | எதிரணியின் வேகத்தைத் தணிக்கும் மென்மையான கட்டுப்பாட்டு அடிப்பு. |
| drop serve | டிராப் சர்வ் | கைவிடப்பட்டு துள்ளிய பந்தை அடித்துச் செய்யும் சர்வ். |
| two-bounce rule | இரு துள்ளல் விதி | சர்வும் அதன் ரிட்டர்னும் தலா துள்ளிய பிறகே அடிக்கப்பட வேண்டும். |
| volley | வாலி | பந்து தரையில் துள்ளுவதற்கு முன் அடித்தல். |
| lob | லாப் | எதிராளியின் தலைக்கு மேல் பந்தை உயரமாக அனுப்புதல். |
| fault | ஃபால்ட் | ராலியை முடிக்கும் விதிமீறல். |
| around the post | கம்பத்தைச் சுற்றிய அடிப்பு | வலைக் கம்பத்தின் வெளிப்புறமாக அனுப்பப்படும் அடிப்பு. |

### Held-out draft references

**ta-pickleball-01-1 — kitchen**
- English: Wait for the bounce before hitting from the kitchen.
- Draft Tamil: கிச்சனிலிருந்து அடிப்பதற்கு முன் பந்து துள்ளும் வரை காத்திருங்கள்.

**ta-pickleball-01-2 — kitchen**
- English: Her momentum carried her into the kitchen after the volley.
- Draft Tamil: வாலி அடித்த பிறகு அவரது வேகம் அவரைக் கிச்சனுக்குள் கொண்டு சென்றது.

**ta-pickleball-02-1 — non-volley zone**
- English: The non-volley zone line counts as part of the zone.
- Draft Tamil: வாலி தடைப் பகுதியின் கோடும் அந்தப் பகுதியின் ஒரு பகுதியாகும்.

**ta-pickleball-02-2 — non-volley zone**
- English: You may enter the non-volley zone to play a bounced ball.
- Draft Tamil: துள்ளிய பந்தை அடிக்க வாலி தடைப் பகுதிக்குள் செல்லலாம்.

**ta-pickleball-03-1 — dink**
- English: Keep your dink low over the net.
- Draft Tamil: உங்கள் டிங்க் வலைக்கு மேலே தாழ்வாகச் செல்லட்டும்.

**ta-pickleball-03-2 — dink**
- English: They exchanged soft dinks near the kitchen line.
- Draft Tamil: கிச்சன் கோட்டருகே அவர்கள் மென்மையான டிங்க் அடிப்புகளைப் பரிமாறினர்.

**ta-pickleball-04-1 — third shot drop**
- English: Use a third shot drop to move toward the net.
- Draft Tamil: வலையை நோக்கி முன்னேற மூன்றாவது அடிப்பு டிராப் பயன்படுத்துங்கள்.

**ta-pickleball-04-2 — third shot drop**
- English: Her third shot drop landed in the kitchen.
- Draft Tamil: அவரது மூன்றாவது அடிப்பு டிராப் கிச்சனில் விழுந்தது.

**ta-pickleball-05-1 — drive**
- English: Keep the drive low toward the middle.
- Draft Tamil: டிரைவ் நடுப்பகுதியை நோக்கித் தாழ்வாகச் செல்லட்டும்.

**ta-pickleball-05-2 — drive**
- English: His third-shot drive forced a weak reply.
- Draft Tamil: அவரது மூன்றாவது அடிப்பான டிரைவ் எதிராளியிடமிருந்து பலவீனமான பதிலை வரவழைத்தது.

**ta-pickleball-06-1 — paddle**
- English: Hold the paddle in front of your body.
- Draft Tamil: பேடிலை உங்கள் உடலுக்கு முன்னால் வைத்திருங்கள்.

**ta-pickleball-06-2 — paddle**
- English: The ball hit the edge of her paddle.
- Draft Tamil: பந்து அவரது பேடிலின் விளிம்பில் பட்டது.

**ta-pickleball-07-1 — side out**
- English: A side out gives the serve to the other team.
- Draft Tamil: சைட் அவுட் ஏற்பட்டால் சர்வ் உரிமை எதிரணிக்குச் செல்கிறது.

**ta-pickleball-07-2 — side out**
- English: The referee announced side out after the rally.
- Draft Tamil: ராலிக்குப் பிறகு நடுவர் சைட் அவுட் என்று அறிவித்தார்.

**ta-pickleball-08-1 — stacking**
- English: They use stacking to keep the left-hander on the right.
- Draft Tamil: இடக்கை வீரரை வலப்புறத்தில் வைத்திருக்க அவர்கள் ஸ்டாக்கிங் பயன்படுத்துகின்றனர்.

**ta-pickleball-08-2 — stacking**
- English: Practice stacking before using it in a match.
- Draft Tamil: போட்டியில் பயன்படுத்துவதற்கு முன் ஸ்டாக்கிங் பயிற்சி செய்யுங்கள்.

**ta-pickleball-09-1 — reset**
- English: Soften the fast ball with a reset.
- Draft Tamil: வேகமாக வரும் பந்தை ரீசெட் மூலம் மென்மையாக்குங்கள்.

**ta-pickleball-09-2 — reset**
- English: Her reset gave the team time to recover.
- Draft Tamil: அவரது ரீசெட் அணி மீண்டும் நிலைபெற நேரம் கொடுத்தது.

**ta-pickleball-10-1 — drop serve**
- English: Let the ball bounce before hitting a drop serve.
- Draft Tamil: டிராப் சர்வ் அடிப்பதற்கு முன் பந்து துள்ளட்டும்.

**ta-pickleball-10-2 — drop serve**
- English: He chose a drop serve for better control.
- Draft Tamil: மேலும் கட்டுப்பாட்டிற்காக அவர் டிராப் சர்வைத் தேர்ந்தெடுத்தார்.

**ta-pickleball-11-1 — two-bounce rule**
- English: The two-bounce rule applies to the serve and return.
- Draft Tamil: இரு துள்ளல் விதி சர்வுக்கும் ரிட்டர்னுக்கும் பொருந்தும்.

**ta-pickleball-11-2 — two-bounce rule**
- English: Remember the two-bounce rule before moving in to volley.
- Draft Tamil: வாலி அடிக்க முன்னேறுவதற்கு முன் இரு துள்ளல் விதியை நினைவில் கொள்ளுங்கள்.

**ta-pickleball-12-1 — volley**
- English: Do not volley while touching the kitchen line.
- Draft Tamil: கிச்சன் கோட்டைத் தொட்டபடி வாலி அடிக்காதீர்கள்.

**ta-pickleball-12-2 — volley**
- English: She blocked the fast ball with a volley.
- Draft Tamil: அவர் வேகமான பந்தை வாலியால் தடுத்தார்.

**ta-pickleball-13-1 — lob**
- English: A deep lob pushed both opponents back.
- Draft Tamil: ஆழமான லாப் இரண்டு எதிராளிகளையும் பின்னால் நகர வைத்தது.

**ta-pickleball-13-2 — lob**
- English: Watch the wind before attempting a lob.
- Draft Tamil: லாப் அடிக்க முயல்வதற்கு முன் காற்றைக் கவனியுங்கள்.

**ta-pickleball-14-1 — fault**
- English: Touching the kitchen line during a volley is a fault.
- Draft Tamil: வாலி அடிக்கும்போது கிச்சன் கோட்டைத் தொடுவது ஃபால்ட் ஆகும்.

**ta-pickleball-14-2 — fault**
- English: The referee called a fault after the second bounce.
- Draft Tamil: இரண்டாவது துள்ளலுக்குப் பிறகு நடுவர் ஃபால்ட் என்று அறிவித்தார்.

**ta-pickleball-15-1 — around the post**
- English: She hit an around the post shot from outside the sideline.
- Draft Tamil: அவர் பக்கக் கோட்டுக்கு வெளியிலிருந்து கம்பத்தைச் சுற்றிய அடிப்பை அடித்தார்.

**ta-pickleball-15-2 — around the post**
- English: An around the post shot can travel below net height.
- Draft Tamil: கம்பத்தைச் சுற்றிய அடிப்பு வலையின் உயரத்திற்குக் கீழாகச் செல்லலாம்.
