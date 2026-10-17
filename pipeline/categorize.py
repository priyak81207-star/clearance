"""Assign product category and reason groups from raw text (English + Japanese)."""
import re, os
from common import CONFIG, load_json

# (category, english regex, japanese regex) - first match wins. Edit freely.
RULES = [
    ('basmati',   r'basmati',                                              r'バスマティ|バスマチ'),
    ('blends',    r'curry (powder|paste)|masala|spice (mix|blend)|seasoning|mixed spice|garam', r'カレー粉|マサラ|混合スパイス|調味'),
    ('honey',     r'\bhoney\b',                                            r'はちみつ|ハチミツ|蜂蜜'),
    ('herbal',    r'herbal|botanical|ayurved|ashwagandha|supplement|vitamin|moringa|neem|tulsi|amla|triphala|capsule|tablet|extract|kratom|giloy', r'ハーブ|健康食品|サプリ|アシュワガンダ|ビタミン|カプセル'),
    ('shrimp',    r'shrimp|prawn|vannamei|monodon|\bscampi\b',             r'えび|エビ|海老|シュリンプ|プローン'),
    ('fish',      r'\bfish\b|squid|cuttlefish|\bcrab|lobster|octopus|mackerel|tuna|sardine|pangasius|basa\b|seafood|surimi|clam|oyster|mussel|hilsa|ribbonfish|\bmeen\b', r'魚|いか|イカ|たこ|タコ|カニ|蟹|さば|サバ|マグロ|貝|水産'),
    ('mango',     r'mango|amchur|aam\b',                                  r'マンゴー'),
    ('sesame',    r'sesame|\btil\b|tahini',                               r'ごま|ゴマ|胡麻'),
    ('groundnut', r'groundnut|peanut|arachis',                            r'落花生|ピーナッツ|ピーナツ'),
    ('cashew',    r'cashew',                                              r'カシュー'),
    ('chilli',    r'chilli|chili|capsicum|paprika|cayenne|\bmirch|kashmiri|red pepper|hot pepper|bell pepper|jalape|\bgreen pepper', r'とうがらし|唐辛子|トウガラシ|チリ|パプリカ|カイエン'),
    ('pepper',    r'\bpepper\b(?!oni)|peppercorn|piper nigrum', r'こしょう|コショウ|胡椒'),
    ('coriander', r'coriander|dhania|cilantro',                           r'コリアンダー|パクチー|香菜'),
    ('cumin',     r'\bcumin|\bjeera|\bjira\b',                            r'クミン'),
    ('turmeric',  r'turmeric|curcuma|haldi',                              r'ターメリック|ウコン|うこん'),
    ('fenugreek', r'fenugreek|methi\b|kasuri',                            r'フェヌグリーク|フェネグリーク'),
    ('fennel',    r'fennel|saunf',                                        r'フェンネル'),
    ('spices_other', r'ginger|cardamom|elaichi|clove|cinnamon|cassia|ajwain|carom|nutmeg|mace\b|mustard|saffron|asafoetida|hing\b|curry leaf|curry leaves|bay leaf|star anise|spice|garlic powder|onion powder|poppy|tamarind|kokum|dill|celery seed|nigella|kalonji|paprika', r'生姜|しょうが|ショウガ|ジンジャー|カルダモン|クローブ|丁子|シナモン|ナツメグ|からし|マスタード|サフラン|スパイス|香辛料|ヒング|アジョワン|八角|ニゲラ'),
    ('rice',      r'\brice\b|\bpoha\b|paddy|parboiled|idli|\bdosa\b|\bmurmura|puffed rice', r'米|精米|玄米|ライス|もち'),
    ('wheat',     r'wheat|\batta\b|flour|semolina|\bsuji\b|\brava\b|millet|\bragi\b|bajra|jowar|sorghum|oats?\b|maize|corn\b|barley|\bgram flour|besan|cereal', r'小麦|ミレット|雑穀|とうもろこし|オート|大麦|穀'),
    ('pulses',    r'pulses?|lentil|\bdal\b|\bdhal\b|chickpea|chick pea|\bchana\b|moong|\bmung|\burad\b|\btoor\b|\btur\b|rajma|kidney bean|\bbeans?\b|pigeon pea|cowpea|soya|soy bean|soybean|peas\b', r'豆|レンズ|ダル|ひよこ'),
    ('tea',       r'\btea\b|chai|darjeeling|assam|matcha',                r'茶|紅茶|ティー'),
    ('coffee',    r'coffee',                                              r'コーヒー|珈琲'),
    ('dairy',     r'\bghee\b|milk|paneer|butter|cheese|yogh?urt|\bcurd\b|\bkhoa\b|\bmava\b|\bdairy|lassi|\bcream\b', r'ギー|乳|チーズ|バター|ヨーグルト'),
    ('meat',      r'\bmeat|\bbeef|buffalo|mutton|\blamb\b|chicken|poultry|\begg|\bgoat\b|\bpork', r'肉|鶏|卵|牛'),
    ('beverages', r'juice|beverage|drink|soda|squash|syrup|sharbat|energy|water\b|coconut water|cola|mirinda|lassi', r'ジュース|飲料|清涼|ドリンク'),
    ('oils_sugar',r'\boil\b|\bsugar\b|jaggery|\bgur\b|molasses|vanaspati|coconut oil|sunflower|palm|margarine|\bsalt\b', r'油|砂糖|ジャガリー|塩'),
    ('veg',       r'okra|bhindi|gourd|brinjal|aubergine|eggplant|drumstick|moringa pod|spinach|cabbage|cauliflower|\bbeet|carrot|cucumber|vegetable|\bonion|potato|tomato|betel|\bpaan\b|green chill|lady.?finger|ladies|karela|bitter|tinda|tindora|radish|capsicum|pumpkin|sweet potato|yam\b|taro|leaf|leaves|herbs?\b|mint|coriander leaves|fresh beans|cluster bean|guar', r'オクラ|ゴーヤ|なす|ナス|野菜|ほうれん草|ビンロウ|トマト|玉ねぎ|じゃがいも|かぼちゃ|葉'),
    ('fruit_other',r'banana|grape|pomegranate|lychee|litchi|pineapple|melon|papaya|guava|orange|lemon|lime\b|apple|citrus|jackfruit|fruit|dates?\b|fig\b|kiwi|pear\b|plum|berry|berries|mosambi|sapota|chikoo|custard|coconut(?! oil| water)', r'バナナ|ぶどう|ブドウ|ざくろ|ライチ|パイナップル|メロン|パパイヤ|グアバ|オレンジ|柑橘|果実|ナツメヤシ|ココナッツ'),
    ('nuts_other',r'almond|walnut|pistachio|\bnuts?\b|raisin|dried fruit|seed|flax|linseed|chia|psyllium|isabgol|sunflower seed|pumpkin seed|watermelon seed|melon seed|areca|supari|makhana|fox nut|lotus|dry fruit', r'アーモンド|くるみ|クルミ|ピスタチオ|ナッツ|種|干しぶどう|レーズン'),
    ('processed_fv', r'pickle|chutney|puree|paste|canned|tinned|jam\b|preserve|sauce|ketchup|dehydrated|frozen (veg|fruit)|achar', r'漬|ピクルス|チャツネ|ペースト|缶詰|ジャム|ソース|乾燥野菜'),
    ('snacks',    r'snack|biscuit|cookie|bakery|bread|cake|noodle|pasta|namkeen|bhujia|\bpapad|papadum|poppadom|chips|crisps|sweet|candy|chocolate|confection|laddu|halwa|ready (meal|to eat)|instant|vermicelli|mix\b|premix|cracker|wafer|farfar|\bdosa\b|kachori|samosa|mithai|gulab|jalebi|soan|ice cream|dessert|baby food|infant', r'スナック|菓子|ビスケット|パパド|麺|クッキー|パン|チョコ|ナムキーン|インスタント|即席|離乳食'),
]
_COMPILED = [(c, re.compile(e, re.I), re.compile(j) if j else None) for c, e, j in RULES]


def categorize(text):
    t = str(text or '')
    for cat, en, ja in _COMPILED:
        if en.search(t) or (ja and ja.search(t)):
            return cat
    return 'food_other'


# ------------------------------------------------------------------ reasons
REASON_RULES = [
    ('pesticide', r'pesticide|residue|\bmrl\b|chlorpyrifos|ethylene oxide|2-chloroethanol|carbendazim|tricyclazole|acephate|profenofos|monocrotophos|thiamethoxam|imidacloprid|cypermethrin|buprofezin|\bddt\b|fipronil|残留農薬|農薬|残留基準'),
    ('mycotoxin', r'aflatoxin|ochratoxin|mycotoxin|zearalenone|deoxynivalenol|patulin|fumonisin|アフラトキシン|オクラトキシン|カビ毒'),
    ('microbial', r'salmonella|listeria|e\.? ?coli|escherichia|coliform|bacillus|cereus|staphylococ|vibrio|campylobacter|clostridium|enterobacter|mould|mold\b|yeast|microb|bacteria|norovirus|hepatitis|total plate|plate count|大腸菌|サルモネラ|細菌|一般生菌|カビ|腸炎'),
    ('toxin',     r'pyrrolizidine|tropane|alkaloid|natural toxin|hydrocyanic|prussic|cyanide|solanine|ピロリジジン|アルカロイド'),
    ('vetdrug',   r'veterinary|nitrofuran|chloramphenicol|antibiotic|malachite|leucomalachite|oxytetracycline|furazolidone|sulfonamide|動物用医薬品|抗生'),
    ('chemical',  r'cadmium|lead\b|mercury|arsenic|heavy metal|mineral oil|\bpah\b|benzo|dioxin|melamine|nickel|\bcopper\b|\bzinc\b|\btin\b|metal|migration|3-mcpd|acrylamide|sulphur dioxide|sulfur dioxide|nitrate|カドミウム|鉛|水銀|ヒ素|重金属'),
    ('additive',  r'additive|colou?r|dye|sudan|rhodamine|sulphite|sulfite|benzoate|sorbate|preservative|not permitted|unauthori[sz]ed|unlisted|sweetener|flavour|添加物|着色|保存料|指定外|漂白'),
    ('drugclaim', r'drug|medicin|novel food|health claim|therapeutic|cure|treat|sildenafil|tadalafil|steroid|unapproved|医薬品|効能'),
    ('label',     r'label|misbrand|undeclared|allergen|mislead|ingredient list|nutrition|expiry|date mark|shelf life|declaration|origin claim|organic|表示|アレルゲン|期限'),
    ('filth',     r'filth|insect|infest|rodent|decompos|putrid|unsanitary|insanitary|foreign (body|matter|object)|hair\b|dirt|mites?\b|weevil|beetle|moth|worm|pest(?!icide)|不衛生|異物'),
    ('pest',      r'fruit fly|quarantine|phytosanitary|plant health|plant protection|pest(?!icide)|fumigat|vapou?r heat|検疫|植物防疫|ミバエ'),
    ('docs',      r'document|certificate|licen[cs]e|paperwork|identity check|physical check|not accompanied|registration|no process|lacks firm|import permit|証明書|書類|届出'),
]
_RR = [(k, re.compile(p, re.I)) for k, p in REASON_RULES]


def reasons_from(*texts):
    t = ' | '.join(str(x or '') for x in texts)
    out = []
    for k, rx in _RR:
        if rx.search(t) and k not in out:
            out.append(k)
    # Pesticide wording often co-occurs with 'contaminat'; keep the specific cause only
    if 'pesticide' in out and 'filth' in out and not re.search(r'insect|filth|rodent|infest', t, re.I):
        out.remove('filth')
    return out[:3] or ['other']
