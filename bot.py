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
        'title': 'ADCキャリー',
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
            description="参加者の皆さん、`/secret_role` コマンドで自分のロールを確認してください！",
            color=0x0099ff
        )
        
        participant_text = ""
        for user, data in assignments.items():
            participant_text += f"{user.mention} (数字: {data['number']})\n"
        
        embed.add_field(name="🎯 参加者", value=participant_text, inline=False)
        embed.add_field(name="🔍 ロール確認", value="`/secret_role` コマンドを実行すると、あなただけにロールが表示されます", inline=False)
        
        # 参加者に通知するためのメンションを作成
        mentions = " ".join([user.mention for user in assignments.keys()])
        
        await interaction.followup.send(f"🎉 {mentions}", embed=embed)
    else:
        await interaction.followup.send("ロールを割り当てできませんでした。")

@bot.tree.command(name='secret_role', description='秘密のロール決めを開始します（参加者のみに表示）')
@discord.app_commands.describe(
    excluded_roles='除外するロール（スペース区切り）例: top mid'
)
async def secret_role_assignment(interaction: discord.Interaction, excluded_roles: str = None):
    """
    秘密のロール決めを開始するスラッシュコマンド
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
        title="🔒 秘密のロール決め開始！",
        description=f"参加したい人は1〜5の数字でリアクションしてください！{excluded_text}",
        color=0x9932cc
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
    embed.add_field(name="⚠️ 注意", value="結果は参加者にのみ個別通知されます", inline=False)
    embed.set_footer(text="参加者が揃ったら🎲で抽選開始（5分でタイムアウト）")
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # 利用可能なロール数分だけ数字の絵文字を追加
    for num in display_numbers:
        await message.add_reaction(num)
    
    # 抽選開始用の絵文字を追加
    await message.add_reaction('🎲')
    
    # リアクション監視を開始
    await monitor_secret_lottery_reaction(interaction, message, available_roles)

async def monitor_secret_lottery_reaction(interaction, message, available_roles):
    """
    秘密抽選開始リアクションを監視する
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
            title="🔒 秘密抽選中...",
            description="ロールを決めています...",
            color=0xffff00
        )
        await interaction.followup.send(embed=lottery_embed)
        
        # 少し待機（演出）
        await asyncio.sleep(2)
        
        # メッセージを再取得してリアクションを確認
        try:
            message = await interaction.channel.fetch_message(message.id)
            await assign_secret_roles(interaction, message, available_roles)
        except discord.NotFound:
            await interaction.followup.send("メッセージが見つかりません。")
            
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ タイムアウト",
            description="5分間反応がなかったため、秘密ゲームを終了しました。",
            color=0xff0000
        )
        await interaction.followup.send(embed=timeout_embed)

async def assign_secret_roles(interaction, message, available_roles):
    """
    秘密ロール割り当て処理
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
    
    # 結果をチャンネルに表示（参加者数のみ）
    if assignments:
        embed = discord.Embed(
            title="🔒 秘密ロール割り当て完了！",
            description=f"参加者 {len(assignments)} 人に個別でロール結果を送信しました。",
            color=0x9932cc
        )
        embed.add_field(name="🔒 プライバシー", value="各参加者にのみロール結果が通知されています", inline=False)
        
        await interaction.followup.send(embed=embed)
        
        # 各参加者にephemeralでロール結果を送信
        for user, data in assignments.items():
            try:
                role_data = ROLE_MESSAGES[data['role']]
                role_name = ROLES[data['role']]
                
                secret_embed = discord.Embed(
                    title=f"🔒 {role_data['emoji']} あなたの秘密ロール: {role_data['title']}",
                    description=role_data['message'],
                    color=0x9932cc
                )
                secret_embed.add_field(name="🎯 選んだ数字", value=data['number'], inline=True)
                secret_embed.add_field(name="🎮 ロール", value=role_name, inline=True)
                secret_embed.add_field(name="💡 アドバイス", value=role_data['tips'], inline=False)
                secret_embed.add_field(name="🔒 機密情報", value="このロールは他の参加者には秘密です", inline=False)
                
                # ephemeralメッセージで個別通知
                await interaction.followup.send(f"{user.mention}", embed=secret_embed, ephemeral=True)
                
                # 少し待機（Discordのレート制限対策）
                await asyncio.sleep(0.5)
                
            except Exception as e:
                # エラーが発生した場合はログに記録
                print(f"ユーザー {user.name} への通知エラー: {e}")
                await interaction.followup.send(f"⚠️ {user.mention} への通知に失敗しました。", ephemeral=True)
    else:
        await interaction.followup.send("ロールを割り当てできませんでした。")

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