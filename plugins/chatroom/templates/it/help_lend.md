    python "{{CHAT}}" task help T3 NAME --scope "cosa è dentro, cosa è fuori" --files a.py --done-when "la prova" --note "contesto" --as {{AS}} --room "{{ROOM}}"
                                                                       (presta un pezzo del TUO task a chi aspetta: un task tutto suo,
                                                                       suo finché non è fatto; tu nel frattempo non tocchi quei file)
    python "{{CHAT}}" task accept T9 --as {{AS}} --room "{{ROOM}}"   (un pezzo prestato a te: accettalo subito, altrimenti dopo 10 min torna indietro)
    python "{{CHAT}}" task giveback T9 --note "a che punto sei" --as {{AS}} --room "{{ROOM}}"   (restituisci un pezzo prestato)
