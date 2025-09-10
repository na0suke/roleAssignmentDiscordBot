import discord
from discord.ext import commands
import random
import asyncio
import os

# Botの設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ロールの定義
ROLES = {
    'top': 'トップ',
    'jg': 'ジャングル', 
    'mid': 'ミッド',
    'adc': 'ADC',
    'sup': 'サポート'
}

# ロール毎のメッセージ
ROLE_MESSAGES = {
    'top': {
        'emoji': '⚔️',
        'title': 'トップレーナー',
        'message': 'トップが育つともう手に負えない！責任重大なレーンです！',
        'tips': '目が合ったら殺せ'
    },
    'jg': {
        'emoji': '🌲',
        'title': 'ジャングラー',
        'message': 'チームの指揮官、マップ全体をコントロールして勝利に導く責任重大なロールです。',
        'tips': 'ガンク！ガンク！'
    },
    'mid': {
        'emoji': '⚡',
        'title': 'ミッドレーナー',
        'message': 'あなたはチームの中核です！ゲームをキャリーするのが役目！責任重大です！',
        'tips': 'ゲームメイク、ゲームメイク'
    },
    'adc': {
        'emoji': '🏹',
        'title': 'ADC',
        'message': 'あなたがダメージ出せないならチームは負けます！責任重大です！',
        'tips': 'ダメージ！ダメージ！'
    },
    'sup': {
        'emoji': '🛡️',
        'title': 'サポーター',
        'message': '味方を援護し、視界をコントロールする責任重大なロールです！',
        'tips': '怠けるな'
    }
}

# ロール結果を保存
role_results = {}

@bot.event
async def on_ready():
    print(f'{bot.user} がログインしました！')
    # スラッシュコマンドを同期
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} 個のスラッシュコマンドを同期しました")
    except Exception as e:
        print(f"スラッシュコマンドの同期に失敗しました: {e}")

@bot.tree.command(name='role', description='LoLのロール決めを開始します')
@discord.app_commands.describe(
    excluded_roles='除外するロール（スペース区切り）例: top mid'
)
async def start_role_assignment(interaction: discord.Interaction, excluded_roles: str = None):
    """
    ロール決めを開始するスラッシュコマンド
    """
    # 除外ロールの処理
    excluded = set()
    if excluded_roles:
        roles_list = excluded_roles.lower().split()
        for role in roles_list:
            if role in ROLES:
                excluded.add(role)
            else:
                await interaction.response.send_message(
                    f"'{role}' は無効なロールです。利用可能なロール: {', '.join(ROLES.keys())}", 
                    ephemeral=True
                )
                return
    
    available_roles = [role for role in ROLES.keys() if role not in excluded]
    
    if len(available_roles) == 0:
        await interaction.response.send_message("全てのロールが除外されています！", ephemeral=True)
        return
    
    excluded_text = f" (除外: {', '.join(excluded)})" if excluded else ""
    embed = discord.Embed(
        title="🎯 LoLロール決め開始！",
        description=f"参加したい人は1〜5の数字でリアクションしてください！{excluded_text}",
        color=0x00ff00
    )
    embed.add_field(name="利用可能なロール", value=f"{', '.join([ROLES[role] for role in available_roles])}", inline=False)
    
    # 利用可能なロール数に応じてリアクション数を決定
    max_participants = len(available_roles)
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
    display_numbers = number_emojis[:max_participants]
    
    participation_text = f"{' '.join(display_numbers)} のいずれかでリアクション"
    embed.add_field(name="参加方法", value=participation_text, inline=False)
    embed.add_field(name="抽選開始", value="🎲 をクリックして抽選スタート！", inline=False)
    embed.add_field(name="参加可能人数", value=f"最大 {max_participants} 人", inline=False)
    embed.set_footer(text="参加者が揃ったら🎲で抽選開始（5分でタイムアウト）")
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # 利用可能なロール数分だけ数字の絵文字を追加
    for num in display_numbers:
        await message.add_reaction(num)
    
    # 抽選開始用の絵文字を追加
    await message.add_reaction('🎲')
    
    # リアクション監視を開始
    await monitor_lottery_reaction(interaction, message, available_roles)

async def monitor_lottery_reaction(interaction, message, available_roles):
    """
    抽選開始リアクションを監視する
    """
    def check(reaction, user):
        return (reaction.message.id == message.id and 
                str(reaction.emoji) == '🎲' and 
                not user.bot)
    
    try:
        # 抽選開始リアクションを待機
        reaction, user = await bot.wait_for('reaction_add', timeout=300.0, check=check)  # 5分でタイムアウト
        
        # 抽選開始メッセージ
        lottery_embed = discord.Embed(
            title="🎰 抽選中...",
            description="ロールを決めています...",
            color=0xffff00
        )
        await interaction.followup.send(embed=lottery_embed)
        
        # 少し待機（演出）
        await asyncio.sleep(2)
        
        # メッセージを再取得してリアクションを確認
        try:
            message = await interaction.channel.fetch_message(message.id)
            await assign_roles(interaction, message, available_roles)
        except discord.NotFound:
            await interaction.followup.send("メッセージが見つかりません。")
            
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ タイムアウト",
            description="5分間反応がなかったため、ゲームを終了しました。",
            color=0xff0000
        )
        await interaction.followup.send(embed=timeout_embed)

async def assign_roles(interaction, message, available_roles):
    """
    実際にロールを割り当てる処理
    """
    participants = {}
    
    # リアクションから参加者を収集
    number_map = {'1️⃣': 1, '2️⃣': 2, '3️⃣': 3, '4️⃣': 4, '5️⃣': 5}
    
    for reaction in message.reactions:
        if reaction.emoji in number_map:
            async for user in reaction.users():
                if not user.bot:  # Botを除外
                    user_number = number_map[reaction.emoji]
                    if user.id not in participants:  # 重複参加防止
                        participants[user.id] = {
                            'user': user,
                            'number': user_number
                        }
    
    if len(participants) == 0:
        await interaction.followup.send("参加者がいません！")
        return
    
    # ロール割り当て
    assignments = {}
    
    # 参加者をシャッフル
    participant_list = list(participants.values())
    random.shuffle(participant_list)
    
    # ロールを割り当て
    for i, participant in enumerate(participant_list):
        if i < len(available_roles):
            role = available_roles[i]
            assignments[participant['user']] = {
                'role': role,
                'number': participant['number']
            }
    
    # 結果を保存（チャンネルとゲームIDで識別）
    game_id = f"{interaction.channel_id}_{message.id}"
    role_results[game_id] = assignments
    
    # 結果をチャンネルに表示（参加者のみ表示、ロールは隠す）
    if assignments:
        embed = discord.Embed(
            title="🎊 ロール割り当て完了！",
            description="チャンネルでロール結果を確認してください！",
            color=0x0099ff
        )
        
        result_text = ""
        for user, data in assignments.items():
            role_name = ROLES[data['role']]
            role_emoji = ROLE_MESSAGES[data['role']]['emoji']
            result_text += f"{user.mention} (数字: {data['number']}) → **{role_emoji} {role_name}**\n"
        
        embed.add_field(name="🎯 ロール割り当て結果", value=result_text, inline=False)
        
        # 参加者に通知するためのメンションを作成
        mentions = " ".join([user.mention for user in assignments.keys()])
        
        await interaction.followup.send(f"🎉 {mentions}", embed=embed)
    else:
        await interaction.followup.send("ロールを割り当てできませんでした。")

@bot.tree.command(name='secret_role', description='秘密のロール決めを開始します（VC参加者限定）')
@discord.app_commands.describe(
    excluded_roles='除外するロール（スペース区切り）例: top mid'
)
async def secret_role_assignment(interaction: discord.Interaction, excluded_roles: str = None):
    """
    秘密のロール決めを開始するスラッシュコマンド（VC参加者限定）
    """
    # 除外ロールの処理
    excluded = set()
    if excluded_roles:
        roles_list = excluded_roles.lower().split()
        for role in roles_list:
            if role in ROLES:
                excluded.add(role)
            else:
                await interaction.response.send_message(
                    f"'{role}' は無効なロールです。利用可能なロール: {', '.join(ROLES.keys())}", 
                    ephemeral=True
                )
                return
    
    available_roles = [role for role in ROLES.keys() if role not in excluded]
    
    if len(available_roles) == 0:
        await interaction.response.send_message("全てのロールが除外されています！", ephemeral=True)
        return
    
    # ロールをランダムにシャッフル
    shuffled_roles = available_roles.copy()
    random.shuffle(shuffled_roles)
    
    excluded_text = f" (除外: {', '.join(excluded)})" if excluded else ""
    
    # コマンド実行者のVC参加者を取得
    command_user = interaction.user
    vc_members = []
    vc_channel_name = None
    
    if command_user.voice and command_user.voice.channel:
        vc_channel = command_user.voice.channel
        vc_members = [member for member in vc_channel.members if not member.bot]
        vc_channel_name = vc_channel.name
        
        if len(vc_members) < len(available_roles):
            await interaction.response.send_message(
                f"⚠️ VC参加者が不足しています。必要: {len(available_roles)}人、現在: {len(vc_members)}人", 
                ephemeral=True
            )
            return
    else:
        await interaction.response.send_message(
            "⚠️ ボイスチャンネルに参加してからコマンドを実行してください。", 
            ephemeral=True
        )
        return
    
    # 一時的チャンネルを作成
    guild = interaction.guild
    category = interaction.channel.category  # 現在のチャンネルと同じカテゴリに作成
    
    # チャンネル権限を設定（VC参加者のみアクセス可能）
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),  # @everyone は見えない
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)  # Bot権限のみ
    }
    
    # VC参加者にのみ権限を付与
    for member in vc_members:
        overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True, add_reactions=True)
    
    # 管理者権限を持つ人も明示的に除外（VC参加者でない場合）
    vc_member_ids = {member.id for member in vc_members}
    for member in guild.members:
        if member.guild_permissions.administrator and member.id not in vc_member_ids and not member.bot:
            overwrites[member] = discord.PermissionOverwrite(read_messages=False)  # 管理者でもVC非参加なら見えない
    
    # 一時チャンネル作成
    temp_channel_name = f"🔒role-決め-{vc_channel_name.lower()}"
    temp_channel = await guild.create_text_channel(
        name=temp_channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"🎤 {vc_channel_name} 参加者限定のロール決め"
    )
    
    # 元のチャンネルで案内メッセージ
    vc_member_list = ", ".join([member.display_name for member in vc_members])
    guide_embed = discord.Embed(
        title="🎤 VC限定ロール決め開始",
        description=f"**{vc_channel_name}** 参加者専用チャンネルを作成しました！",
        color=0x9932cc
    )
    guide_embed.add_field(name="📍 専用チャンネル", value=f"{temp_channel.mention}", inline=False)
    guide_embed.add_field(name="👥 対象者", value=vc_member_list, inline=False)
    guide_embed.add_field(name="⚠️ 注意", value="ロール決め完了後、チャンネルは自動削除されます", inline=False)
    
    await interaction.response.send_message(embed=guide_embed)
    
    # 専用チャンネルでロール決めメッセージを送信
    embed = discord.Embed(
        title="🔒 秘密のロール決め開始！",
        description=f"数字を選ぶと即座にロールが決定されます！{excluded_text}",
        color=0x9932cc
    )
    
    embed.add_field(name="🎤 対象VC", value=f"**{vc_channel_name}**", inline=False)
    embed.add_field(name="👥 参加者", value=vc_member_list, inline=False)
    
    # 利用可能なロール数に応じてリアクション数を決定
    max_participants = len(available_roles)
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
    display_numbers = number_emojis[:max_participants]
    
    # 数字とロールの対応を表示（ロール名は隠す）
    participation_text = f"{' '.join(display_numbers)} から選択してください"
    embed.add_field(name="参加方法", value=participation_text, inline=False)
    embed.add_field(name="利用可能なロール", value=f"{', '.join([ROLES[role] for role in available_roles])}", inline=False)
    embed.add_field(name="⚠️ 重要", value="数字を選ぶと即座にロールが確定します！", inline=False)
    embed.add_field(name="🔒 プライバシー", value="結果はチャンネル内で表示されます", inline=False)
    embed.set_footer(text="一度選択すると変更できません")
    
    message = await temp_channel.send(embed=embed)
    
    # 利用可能なロール数分だけ数字の絵文字を追加
    for num in display_numbers:
        await message.add_reaction(num)
    
    # 数字とロールの対応を保存
    role_mapping = {}
    for i, role in enumerate(shuffled_roles):
        if i < len(display_numbers):
            role_mapping[display_numbers[i]] = role
    
    # 選択済みロールを管理
    selected_roles = set()
    
    # リアクション監視を開始
    await monitor_temp_channel_role_selection(interaction, message, role_mapping, selected_roles, temp_channel)

async def monitor_temp_channel_role_selection(interaction, message, role_mapping, selected_roles, temp_channel):
    """
    一時チャンネルでの数字リアクションを監視して即座にロール決定
    """
    def check_number_reaction(reaction, user):
        return (reaction.message.id == message.id and 
                str(reaction.emoji) in role_mapping.keys() and 
                not user.bot)
    
    try:
        while len(selected_roles) < len(role_mapping):
            reaction, user = await bot.wait_for('reaction_add', timeout=300.0, check=check_number_reaction)
            
            selected_emoji = str(reaction.emoji)
            assigned_role = role_mapping[selected_emoji]
            
            # 重複チェック
            if assigned_role in selected_roles:
                # すでに選択済みのロールの場合
                duplicate_embed = discord.Embed(
                    title="⚠️ 既に選択済み",
                    description=f"数字 {selected_emoji} のロールは既に他の人が選択しています。\n{user.mention} は別の数字を選んでください。",
                    color=0xff9900
                )
                await temp_channel.send(embed=duplicate_embed)
                continue
            
            # ロールを確定
            selected_roles.add(assigned_role)
            
            # ユーザーに結果を通知（普通のメッセージ）
            role_data = ROLE_MESSAGES[assigned_role]
            role_name = ROLES[assigned_role]
            number_index = list(role_mapping.keys()).index(selected_emoji) + 1
            
            result_embed = discord.Embed(
                title=f"{role_data['emoji']} {user.display_name} のロール: {role_data['title']}",
                description=role_data['message'],
                color=0x9932cc
            )
            result_embed.add_field(name="🎯 選んだ数字", value=f"{selected_emoji} (番号: {number_index})", inline=True)
            result_embed.add_field(name="🎮 確定ロール", value=role_name, inline=True)
            result_embed.add_field(name="💡 アドバイス", value=role_data['tips'], inline=False)
            
            await temp_channel.send(embed=result_embed)
            
            # 進行状況を表示
            progress_embed = discord.Embed(
                title="🔒 秘密ロール選択中...",
                description=f"参加者: {len(selected_roles)}/{len(role_mapping)} 人がロール決定",
                color=0x9932cc
            )
            if len(selected_roles) == len(role_mapping):
                progress_embed.add_field(name="✅ 完了", value="全てのロールが決定しました！\n30秒後にこのチャンネルを削除します", inline=False)
                await temp_channel.send(embed=progress_embed)
                
                # 30秒待ってからチャンネル削除
                await asyncio.sleep(30)
                try:
                    await temp_channel.delete()
                except:
                    print(f"チャンネル削除失敗: {temp_channel.name}")
                break
            else:
                remaining_numbers = [emoji for emoji, role in role_mapping.items() if role not in selected_roles]
                progress_embed.add_field(name="🎯 残り選択肢", value=' '.join(remaining_numbers), inline=False)
                await temp_channel.send(embed=progress_embed)
                
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ タイムアウト",
            description="5分間反応がなかったため、秘密ロール決めを終了しました。\n30秒後にこのチャンネルを削除します。",
            color=0xff0000
        )
        await temp_channel.send(embed=timeout_embed)
        await asyncio.sleep(30)
        try:
            await temp_channel.delete()
        except:
            print(f"チャンネル削除失敗: {temp_channel.name}")

# ロール除外データを保存する辞書
user_role_exclusions = {}

# ロール文字のマッピング
ROLE_LETTERS = {
    '⚔️': 'top',
    '🌲': 'jg', 
    '🪄': 'mid',
    '🏹': 'adc',
    '❤️': 'sup'
}

@bot.tree.command(name='exclude_role', description='VC参加者限定：やりたくないロールを選んでからロール分けします')
async def exclude_role_assignment(interaction: discord.Interaction):
    """
    VC参加者限定でやりたくないロールを除外してロール分けを行う
    """
    # コマンド実行者のVC参加者を取得
    command_user = interaction.user
    vc_members = []
    vc_channel_name = None
    
    if command_user.voice and command_user.voice.channel:
        vc_channel = command_user.voice.channel
        vc_members = [member for member in vc_channel.members if not member.bot]
        vc_channel_name = vc_channel.name
        
        if len(vc_members) < 2:
            await interaction.response.send_message(
                "⚠️ VC参加者が2人以上必要です。", 
                ephemeral=True
            )
            return
        elif len(vc_members) > 5:
            member_list = ", ".join([member.display_name for member in vc_members])
            await interaction.response.send_message(
                f"⚠️ **VC参加者が多すぎます**\n" +
                f"現在: **{len(vc_members)}人** / 最大: **5人**\n\n" +
                f"**参加者一覧**: {member_list}\n\n" +
                f"💡 **解決方法**:\n" +
                f"• **5人まで減らす**: 一部のメンバーが一時退出\n" +
                f"• **別のVC作成**: チームを分ける\n" +
                f"• **通常の `/role` 使用**: リアクション参加型\n" +
                f"• **2回に分けて実行**: 5人ずつでロール決め",
                ephemeral=True
            )
            return
    else:
        await interaction.response.send_message(
            "⚠️ ボイスチャンネルに参加してからコマンドを実行してください。", 
            ephemeral=True
        )
        return
    
    # 除外設定をリセット
    session_id = f"{interaction.channel_id}_{vc_channel.id}"
    user_role_exclusions[session_id] = {}
    
    # VC参加者リスト
    vc_member_list = ", ".join([member.display_name for member in vc_members])
    
    # 除外ロール選択のメッセージ
    embed = discord.Embed(
        title="🚫 やりたくないロール選択",
        description=f"**{vc_channel_name}** 参加者限定\n\nやりたくないロールをリアクションで選択してください！",
        color=0xff6b6b
    )
    embed.add_field(name="🎤 対象VC", value=f"**{vc_channel_name}**", inline=False)
    embed.add_field(name="👥 参加者", value=vc_member_list, inline=False)
    embed.add_field(name="📋 手順", value="1️⃣ やりたくないロールを選択\n2️⃣ 選択完了後 ▶️ でロール分け実行", inline=False)
    embed.add_field(name="⚠️ 注意", value="• 複数のロールを除外可能\n• どれも選択しなければ全ロール候補", inline=False)
    
    # ロール選択肢を表示
    role_list = ""
    for letter, role_key in ROLE_LETTERS.items():
        role_name = ROLES[role_key]
        role_list += f"{letter} → {role_name}\n"
    
    embed.add_field(name="🎯 除外可能なロール", value=role_list, inline=False)
    embed.add_field(name="💡 ヒント", value="リアクションなし = どのロールでもOK", inline=False)
    embed.set_footer(text="除外選択完了後、▶️ で実行開始！")
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # ロール除外用の文字リアクションを追加
    for letter in ROLE_LETTERS.keys():
        await message.add_reaction(letter)
    
    # 実行開始用の絵文字を追加
    await message.add_reaction('▶️')
    
    # リアクション監視を開始
    await monitor_exclusion_and_lottery(interaction, message, vc_members, session_id)

async def monitor_exclusion_and_lottery(interaction, message, vc_members, session_id):
    """
    除外リアクションと実行開始を監視
    """
    vc_member_ids = {member.id for member in vc_members}
    
    def check_exclusion_reaction(reaction, user):
        return (reaction.message.id == message.id and 
                user.id in vc_member_ids and 
                str(reaction.emoji) in ROLE_LETTERS.keys())
    
    def check_execute_reaction(reaction, user):
        return (reaction.message.id == message.id and 
                str(reaction.emoji) == '▶️' and 
                user.id in vc_member_ids)
    
    try:
        while True:
            # 除外リアクションまたは実行開始リアクションを待機
            done, pending = await asyncio.wait([
                asyncio.create_task(bot.wait_for('reaction_add', check=check_exclusion_reaction)),
                asyncio.create_task(bot.wait_for('reaction_remove', check=check_exclusion_reaction)),
                asyncio.create_task(bot.wait_for('reaction_add', check=check_execute_reaction))
            ], return_when=asyncio.FIRST_COMPLETED, timeout=300.0)
            
            # 未完了のタスクをキャンセル
            for task in pending:
                task.cancel()
            
            if not done:
                continue
                
            reaction, user = await done.pop()
            
            # 実行開始の場合
            if str(reaction.emoji) == '▶️':
                # 抽選を実行
                await execute_exclusion_lottery(interaction, message, vc_members, session_id)
                break
            
            # 除外ロール選択の場合
            else:
                await handle_exclusion_reaction(interaction, reaction, user, session_id)
                
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ タイムアウト",
            description="5分間反応がなかったため、除外ロール選択を終了しました。",
            color=0xff0000
        )
        await interaction.followup.send(embed=timeout_embed)
        # セッションデータをクリア
        if session_id in user_role_exclusions:
            del user_role_exclusions[session_id]

async def handle_exclusion_reaction(interaction, reaction, user, session_id):
    """
    除外ロールのリアクション処理
    """
    letter = str(reaction.emoji)
    
    # 文字からロールキーを取得
    role_key = ROLE_LETTERS.get(letter)
    if not role_key:
        return
    
    # ユーザーの除外リストを初期化
    if user.id not in user_role_exclusions[session_id]:
        user_role_exclusions[session_id][user.id] = {'user': user, 'excluded_roles': set()}
    
    # メッセージを再取得してリアクション状態を確認
    try:
        message = await interaction.channel.fetch_message(reaction.message.id)
        user_reactions = []
        
        for msg_reaction in message.reactions:
            if str(msg_reaction.emoji) == letter:
                async for reaction_user in msg_reaction.users():
                    if reaction_user.id == user.id:
                        user_reactions.append(letter)
                        break
        
        # リアクションがある場合は除外リストに追加、ない場合は削除
        if letter in user_reactions:
            user_role_exclusions[session_id][user.id]['excluded_roles'].add(role_key)
        else:
            user_role_exclusions[session_id][user.id]['excluded_roles'].discard(role_key)
            
    except discord.NotFound:
        pass

async def execute_exclusion_lottery(interaction, message, vc_members, session_id):
    """
    除外設定を考慮したロール抽選を実行
    """
    # 実行開始メッセージ
    lottery_embed = discord.Embed(
        title="🎰 除外設定を確認中...",
        description="各プレイヤーの除外ロールと参加状況を確認しています...",
        color=0xffff00
    )
    await interaction.followup.send(embed=lottery_embed)
    
    await asyncio.sleep(2)
    
    # 参加者のみをフィルタリング
    participating_members = []
    non_participating_members = []
    
    for member in vc_members:
        is_participating = True
        if member.id in user_role_exclusions[session_id]:
            is_participating = user_role_exclusions[session_id][member.id].get('participating', True)
        
        if is_participating:
            participating_members.append(member)
        else:
            non_participating_members.append(member)
    
    # 参加者が少なすぎる場合
    if len(participating_members) < 2:
        error_embed = discord.Embed(
            title="❌ 参加者不足",
            description=f"ロール決めには最低2人の参加者が必要です。\n現在の参加者: {len(participating_members)}人",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)
        return
    
    # 参加者が多すぎる場合
    if len(participating_members) > 5:
        error_embed = discord.Embed(
            title="❌ 参加者過多",
            description=f"ロール決めの参加者が多すぎます。\n参加者: {len(participating_members)}人 / 最大: 5人\n\n追加で ❌ を押して不参加にしてください。",
            color=0xff0000
        )
        participating_list = ", ".join([member.display_name for member in participating_members])
        error_embed.add_field(name="現在の参加者", value=participating_list, inline=False)
        await interaction.followup.send(embed=error_embed)
        return
    
    # 除外設定の確認と表示
    exclusion_summary = "**🚫 除外設定一覧**\n"
    valid_assignments = []
    
    for member in participating_members:
        excluded_roles = set()
        if member.id in user_role_exclusions[session_id]:
            excluded_roles = user_role_exclusions[session_id][member.id]['excluded_roles']
        
        # 除外されていないロール = 利用可能なロール
        available_roles = [role for role in ROLES.keys() if role not in excluded_roles]
        
        if excluded_roles:
            excluded_names = [ROLES[role] for role in excluded_roles]
            exclusion_summary += f"• {member.display_name}: 除外 {', '.join(excluded_names)}\n"
        else:
            exclusion_summary += f"• {member.display_name}: 除外なし（全ロールOK）\n"
        
        valid_assignments.append({
            'user': member,
            'available_roles': available_roles,
            'excluded_count': len(excluded_roles)
        })
    
    # 不参加者の情報も表示
    if non_participating_members:
        non_participating_list = ", ".join([member.display_name for member in non_participating_members])
        exclusion_summary += f"\n**👥 参加状況**\n"
        exclusion_summary += f"• 参加者: {len(participating_members)}人\n"
        exclusion_summary += f"• 不参加: {non_participating_list}\n"
    
    # 割り当て可能性をチェック
    all_roles = list(ROLES.keys())
    
    # 割り当てアルゴリズム実行
    try:
        assignments = assign_roles_with_exclusions(valid_assignments, all_roles)
        
        if not assignments:
            error_embed = discord.Embed(
                title="❌ 割り当て失敗",
                description="除外設定により、全員にロールを割り当てることができませんでした。\n除外するロールを減らしてください。",
                color=0xff0000
            )
            error_embed.add_field(name="除外状況", value=exclusion_summary, inline=False)
            await interaction.followup.send(embed=error_embed)
            return
        
        # 結果表示
        result_embed = discord.Embed(
            title="🎊 除外設定を考慮したロール割り当て完了！",
            description="各プレイヤーの希望を考慮してロールを決定しました！",
            color=0x00ff88
        )
        
        result_text = ""
        for user, role_key in assignments.items():
            role_name = ROLES[role_key]
            role_emoji = ROLE_MESSAGES[role_key]['emoji']
            result_text += f"{user.mention} → **{role_emoji} {role_name}**\n"
        
        result_embed.add_field(name="🎯 ロール割り当て結果", value=result_text, inline=False)
        result_embed.add_field(name="📊 詳細情報", value=exclusion_summary, inline=False)
        
        # 参加者に通知
        mentions = " ".join([user.mention for user in assignments.keys()])
        await interaction.followup.send(f"🎉 {mentions}", embed=result_embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ システムエラー",
            description="ロール割り当て中にエラーが発生しました。",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)
        print(f"Role assignment error: {e}")
    
    finally:
        # セッションデータをクリア
        if session_id in user_role_exclusions:
            del user_role_exclusions[session_id]

def assign_roles_with_exclusions(valid_assignments, all_roles):
    """
    除外設定を考慮したロール割り当てアルゴリズム
    """
    import random
    
    # 参加者数分のロールをランダムに選択
    available_roles = random.sample(all_roles, len(valid_assignments))
    
    # 制約が厳しい（利用可能ロールが少ない）プレイヤーから順に割り当て
    sorted_assignments = sorted(valid_assignments, key=lambda x: len(x['available_roles']))
    
    # 複数回試行して最適解を見つける
    for attempt in range(100):
        assignments = {}
        used_roles = set()
        success = True
        
        # シャッフルして毎回異なる結果を得る
        current_available_roles = available_roles.copy()
        random.shuffle(current_available_roles)
        assignment_order = sorted_assignments.copy()
        random.shuffle(assignment_order)
        
        for player_data in assignment_order:
            user = player_data['user']
            available_for_user = [role for role in player_data['available_roles'] 
                                 if role in current_available_roles and role not in used_roles]
            
            if not available_for_user:
                success = False
                break
            
            # ランダムに選択
            chosen_role = random.choice(available_for_user)
            assignments[user] = chosen_role
            used_roles.add(chosen_role)
        
        if success and len(assignments) == len(valid_assignments):
            return assignments
        
        # 失敗した場合は、利用可能ロールを再選択して再試行
        if attempt % 10 == 9:  # 10回ごとに利用可能ロールを変更
            available_roles = random.sample(all_roles, len(valid_assignments))
    
    # 100回試行しても解が見つからない場合
    return None

# 旧式のプレフィックスコマンドの案内
@bot.command(name='role')
async def old_role_command(ctx):
    """
    旧式コマンドの案内
    """
    await ctx.send("新しいスラッシュコマンド `/role` を使用してください！\n使い方: `/role` または `/role excluded_roles:top mid`")

# Botを実行
if __name__ == "__main__":
    import logging
    
    logging.basicConfig(level=logging.INFO)
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("DISCORD_TOKEN環境変数が設定されていません")
        exit(1)
    
    print("Botを開始しています...")
    bot.run(token)