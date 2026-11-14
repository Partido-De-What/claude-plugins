    python "{{CHAT}}" task help T3 NAME --scope "what is in, what is out" --files a.py --done-when "the proof" --note "context" --as {{AS}} --room "{{ROOM}}"
                                                                       (lend a piece of YOUR task to someone who waits: a task of its
                                                                       own, theirs until done; you do not touch those files meanwhile)
    python "{{CHAT}}" task accept T9 --as {{AS}} --room "{{ROOM}}"   (a piece lent to you: accept it at once, or in 10 min it goes back)
    python "{{CHAT}}" task giveback T9 --note "where I got to" --as {{AS}} --room "{{ROOM}}"   (give a lent piece back)
