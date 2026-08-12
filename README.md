# Miroir du flux PNC Blog

Re-publie le flux de `blog.projectnightcrawler.dev` sous une forme que les
lecteurs RSS stricts acceptent.

## Le probleme

Le flux amont est valide, mais servi en `text/xml` **sans parametre `charset`**.
La RFC 3023 impose alors de le decoder en `us-ascii` : la declaration
`encoding="utf-8"` du prologue XML est ignoree, l'en-tete HTTP fait autorite.

Le flux contient exactement deux octets non-ASCII — le `©` de la balise
`<copyright>`, a l'octet 335, **avant le premier `<item>`**. Un parseur strict
meurt la et rend un flux sans aucun article. C'est ce que faisait start.me.

Le detour par `rss.diffbot.com` evitait ce probleme (Atom, `application/atom+xml`)
mais en introduisait un autre : Diffbot ne mettait de balise `published` que sur
un article sur quinze, et regenerait `updated` a l'heure du crawl pour tous les
autres. Au tri par date, les quatorze articles sans date passaient devant le
plus recent — d'ou « Random yapping » affiche comme dernier billet.

## La solution

`normalize_feed.py` lit le flux amont et re-emet un RSS 2.0 :

- **strictement ASCII** (tout caractere non-ASCII en reference numerique), donc
  correct quel que soit le charset suppose par le consommateur ;
- **`pubDate` garanti** sur chaque item, tri antechronologique explicite ;
- `guid isPermaLink="true"` stable, base sur l'URL du billet.

Le fichier sort en `.rss`, extension pour laquelle GitHub Pages renvoie
`application/rss+xml; charset=utf-8`.

## Mise en place

Le code est en place ; il reste deux reglages a faire dans l'interface GitHub,
qui ne sont pas accessibles depuis un push :

1. *Settings → Pages* → Source : **Deploy from a branch**, branche `main`,
   dossier **`/docs`**.
2. *Settings → Actions → General* → *Workflow permissions* :
   **Read and write permissions** (le job commite le flux regenere).

Puis *Actions* → « Miroir du flux PNC » → **Run workflow**, pour un premier
passage sans attendre le cron.

Le flux est alors disponible sur :

```
https://kotk1n.github.io/pnc-feed/pnc.rss
```

C'est cette URL a mettre dans start.me, en **supprimant puis recreant** le
widget plutot qu'en editant l'URL en place.

## Verifier

```bash
python3 normalize_feed.py
python3 -c "
d=open('docs/pnc.rss','rb').read()
assert sum(1 for b in d if b>0x7f)==0, 'octets non-ASCII presents'
d.decode('us-ascii')
print('OK : pur ASCII, insensible au charset')
"
```
