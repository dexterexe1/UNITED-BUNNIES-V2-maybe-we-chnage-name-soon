"""
role_info.py — Role Information Commands
Shows server roles with varying levels of detail
"""
import discord
from discord.ext import commands
from typing import Dict, List

from bot.config import bot, style_embed, BRAND_COLOR, BRAND_EMOJI, staff_check, EMOJI_BULLET

# Permission descriptions (short)
PERM_SHORT_DESC = {
    'administrator': '👑 Full Control',
    'manage_guild': '⚙️ Manage Server',
    'manage_roles': '🎭 Manage Roles',
    'manage_channels': '📝 Manage Channels',
    'kick_members': '👢 Kick',
    'ban_members': '🔨 Ban',
    'moderate_members': '🔇 Timeout',
    'manage_messages': '🗑️ Manage Messages',
    'manage_nicknames': '✏️ Manage Nicknames',
    'manage_webhooks': '🔗 Manage Webhooks',
    'manage_emojis': '😀 Manage Emojis',
    'view_audit_log': '📋 View Logs',
    'mention_everyone': '📢 Mention Everyone',
    'send_messages': '💬 Send Messages',
    'manage_threads': '🧵 Manage Threads',
    'create_public_threads': '🧵 Create Threads',
    'send_messages_in_threads': '💬 Send in Threads',
    'attach_files': '📎 Attach Files',
    'embed_links': '🔗 Embed Links',
    'add_reactions': '😊 Add Reactions',
    'external_emojis': '😀 External Emojis',
    'external_stickers': '🎨 External Stickers',
    'connect': '🔊 Connect Voice',
    'speak': '🎤 Speak',
    'mute_members': '🔇 Mute Members',
    'deafen_members': '🔇 Deafen Members',
    'move_members': '↔️ Move Members',
    'use_voice_activation': '🎤 Voice Activity',
}

# Full permission descriptions
PERM_FULL_DESC = {
    'administrator': 'Administrator - Full server control, bypasses all permissions',
    'manage_guild': 'Manage Server - Change server name, region, icon, and settings',
    'manage_roles': 'Manage Roles - Create, edit, and delete roles (lower than their highest role)',
    'manage_channels': 'Manage Channels - Create, edit, and delete channels',
    'kick_members': 'Kick Members - Remove members from the server (they can rejoin)',
    'ban_members': 'Ban Members - Permanently ban members from the server',
    'moderate_members': 'Moderate Members - Timeout members (prevent them from interacting)',
    'manage_messages': 'Manage Messages - Delete messages and pin messages',
    'manage_nicknames': 'Manage Nicknames - Change other members\' nicknames',
    'manage_webhooks': 'Manage Webhooks - Create, edit, and delete webhooks',
    'manage_emojis': 'Manage Emojis and Stickers - Create, edit, and delete emojis/stickers',
    'manage_events': 'Manage Events - Create, edit, and delete scheduled events',
    'view_audit_log': 'View Audit Log - See server audit logs and moderation actions',
    'view_channel': 'View Channels - See channels (can be overridden per channel)',
    'view_guild_insights': 'View Server Insights - Access server analytics',
    'change_nickname': 'Change Nickname - Change their own nickname',
    'mention_everyone': 'Mention @everyone, @here, and All Roles - Ping entire server',
    'read_message_history': 'Read Message History - See past messages in channels',
    'send_messages': 'Send Messages - Send messages in text channels',
    'send_tts_messages': 'Send TTS Messages - Send text-to-speech messages',
    'manage_threads': 'Manage Threads - Rename, delete, archive/unarchive threads',
    'create_public_threads': 'Create Public Threads - Start threads in channels',
    'create_private_threads': 'Create Private Threads - Start private threads',
    'send_messages_in_threads': 'Send Messages in Threads - Reply in threads',
    'attach_files': 'Attach Files - Upload files and media to channels',
    'embed_links': 'Embed Links - Preview links with embeds',
    'add_reactions': 'Add Reactions - React to messages with emojis',
    'use_external_emojis': 'Use External Emojis - Use emojis from other servers',
    'use_external_stickers': 'Use External Stickers - Use stickers from other servers',
    'use_application_commands': 'Use Application Commands - Use slash commands',
    'connect': 'Connect to Voice - Join voice channels',
    'speak': 'Speak in Voice - Talk in voice channels',
    'stream': 'Video/Screen Share - Stream video or share screen',
    'use_embedded_activities': 'Use Activities - Start activities in voice channels',
    'use_soundboard': 'Use Soundboard - Play soundboard sounds',
    'use_external_sounds': 'Use External Sounds - Use sounds from other servers',
    'mute_members': 'Mute Members - Server mute members in voice',
    'deafen_members': 'Deafen Members - Server deafen members in voice',
    'move_members': 'Move Members - Move members between voice channels',
    'use_voice_activation': 'Use Voice Activity - Use voice activity detection (no push-to-talk)',
    'priority_speaker': 'Priority Speaker - Be heard more clearly in voice (louder)',
    'request_to_speak': 'Request to Speak - Request to speak in stage channels',
}


def get_key_permissions(permissions: discord.Permissions) -> List[str]:
    """Get list of important permissions (excluding basic ones)."""
    important_perms = [
        'administrator', 'manage_guild', 'manage_roles', 'manage_channels',
        'kick_members', 'ban_members', 'moderate_members', 'manage_messages',
        'manage_nicknames', 'manage_webhooks', 'view_audit_log', 'mention_everyone',
        'manage_threads', 'manage_emojis', 'manage_events'
    ]
    
    perms = []
    for perm_name in important_perms:
        if getattr(permissions, perm_name, False):
            perms.append(perm_name)
    
    return perms


def get_all_permissions(permissions: discord.Permissions) -> List[str]:
    """Get all enabled permissions."""
    perms = []
    for perm_name, value in permissions:
        if value:
            perms.append(perm_name)
    return perms


def format_role_color(role: discord.Role) -> str:
    """Format role color as hex."""
    if role.color.value == 0:
        return "Default (No Color)"
    return f"#{role.color.value:06x}"


# ==========================================
#         ROLES COMMAND (Simple List)
# ==========================================

@bot.command(name="roles", help="List all server roles (staff only)")
@staff_check(need="mod")
async def roles_cmd(ctx: commands.Context):
    """Show a simple list of all server roles."""
    roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
    
    # Exclude @everyone
    roles = [r for r in roles if r.name != "@everyone"]
    
    if not roles:
        await ctx.send(embed=style_embed(
            title="Server Roles",
            description="This server has no custom roles.",
            kind="info"
        ))
        return
    
    # Split into chunks if too many roles
    role_list = []
    for i, role in enumerate(roles, 1):
        member_count = len(role.members)
        role_list.append(f"{i}. {role.mention} • `{member_count}` member{'s' if member_count != 1 else ''}")
    
    # Create pages if needed
    chunks = []
    chunk_size = 25
    for i in range(0, len(role_list), chunk_size):
        chunks.append(role_list[i:i + chunk_size])
    
    # Send first page
    description = "\n".join(chunks[0])
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Server Roles ({len(roles)} total)",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text=f"{ctx.guild.name} • Page 1/{len(chunks)}")
    
    await ctx.send(embed=embed)
    
    # Send additional pages if needed
    for i, chunk in enumerate(chunks[1:], 2):
        description = "\n".join(chunk)
        embed = style_embed(
            title=f"{BRAND_EMOJI} Server Roles (continued)",
            description=description,
            color=BRAND_COLOR,
            kind="info"
        )
        embed.set_footer(text=f"{ctx.guild.name} • Page {i}/{len(chunks)}")
        await ctx.send(embed=embed)


# ==========================================
#         ROLEINFO COMMAND (Key Permissions)
# ==========================================

@bot.command(name="roleinfo", help="Show role info with key permissions (staff only)")
@staff_check(need="mod")
async def roleinfo_cmd(ctx: commands.Context, *, role: discord.Role = None):
    """Show information about a role including key permissions."""
    
    if role is None:
        # Show all roles with key info
        roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        roles = [r for r in roles if r.name != "@everyone"]
        
        if not roles:
            await ctx.send(embed=style_embed(
                title="Server Roles",
                description="This server has no custom roles.",
                kind="info"
            ))
            return
        
        # Limit to top 10 roles
        roles = roles[:10]
        
        description = ""
        for role in roles:
            key_perms = get_key_permissions(role.permissions)
            member_count = len(role.members)
            
            description += f"**{role.mention}**\n"
            description += f"  {EMOJI_BULLET} Members: `{member_count}`\n"
            description += f"  {EMOJI_BULLET} Color: `{format_role_color(role)}`\n"
            
            if key_perms:
                perm_icons = [PERM_SHORT_DESC.get(p, p) for p in key_perms[:5]]
                description += f"  {EMOJI_BULLET} Perms: {' '.join(perm_icons)}\n"
                if len(key_perms) > 5:
                    description += f"     ... +{len(key_perms) - 5} more\n"
            else:
                description += f"  {EMOJI_BULLET} Perms: No special permissions\n"
            
            description += "\n"
        
        embed = style_embed(
            title=f"{BRAND_EMOJI} Role Information",
            description=description,
            color=BRAND_COLOR,
            kind="info"
        )
        
        embed.set_footer(text=f"Showing top {len(roles)} roles • Use ?roleinfo @role for detailed info")
        
        await ctx.send(embed=embed)
    
    else:
        # Show detailed info for specific role
        key_perms = get_key_permissions(role.permissions)
        member_count = len(role.members)
        
        embed = discord.Embed(
            title=f"Role: {role.name}",
            color=role.color if role.color.value != 0 else BRAND_COLOR,
            timestamp=role.created_at
        )
        
        # Basic info
        embed.add_field(
            name="📊 Basic Info",
            value=f"**ID:** `{role.id}`\n"
                  f"**Members:** `{member_count}`\n"
                  f"**Color:** `{format_role_color(role)}`\n"
                  f"**Position:** `{role.position}`\n"
                  f"**Mentionable:** `{'Yes' if role.mentionable else 'No'}`\n"
                  f"**Hoisted:** `{'Yes' if role.hoist else 'No'}`",
            inline=False
        )
        
        # Key permissions
        if key_perms:
            perm_list = []
            for perm in key_perms:
                icon = PERM_SHORT_DESC.get(perm, perm)
                perm_list.append(icon)
            
            embed.add_field(
                name="🔑 Key Permissions",
                value="\n".join(perm_list) if perm_list else "None",
                inline=False
            )
        
        embed.set_footer(text=f"Created at")
        
        await ctx.send(embed=embed)


# ==========================================
#         ROLEFULLINFO COMMAND (All Permissions)
# ==========================================

@bot.command(name="rolefullinfo", aliases=["roledetails"], help="Show complete role information (staff only)")
@staff_check(need="mod")
async def rolefullinfo_cmd(ctx: commands.Context, *, role: discord.Role):
    """Show complete information about a role including all permissions."""
    
    all_perms = get_all_permissions(role.permissions)
    member_count = len(role.members)
    
    embed = discord.Embed(
        title=f"🔍 Complete Role Information",
        description=f"**Role:** {role.mention}",
        color=role.color if role.color.value != 0 else BRAND_COLOR,
        timestamp=role.created_at
    )
    
    # Basic info
    embed.add_field(
        name="📊 Basic Information",
        value=f"**Name:** {role.name}\n"
              f"**ID:** `{role.id}`\n"
              f"**Members:** `{member_count}`\n"
              f"**Color:** `{format_role_color(role)}`\n"
              f"**Position:** `{role.position}/{len(ctx.guild.roles)}`\n"
              f"**Mentionable:** `{'Yes' if role.mentionable else 'No'}`\n"
              f"**Display Separately:** `{'Yes' if role.hoist else 'No'}`\n"
              f"**Managed:** `{'Yes (Bot/Integration)' if role.managed else 'No'}`",
        inline=False
    )
    
    # Permissions section
    if role.permissions.administrator:
        embed.add_field(
            name="🔑 Permissions",
            value="**👑 ADMINISTRATOR**\n"
                  "This role has full control over the server and bypasses all permission checks.",
            inline=False
        )
    elif all_perms:
        # Group permissions by category
        admin_perms = []
        moderation_perms = []
        text_perms = []
        voice_perms = []
        other_perms = []
        
        for perm in all_perms:
            desc = PERM_FULL_DESC.get(perm, perm.replace('_', ' ').title())
            
            if perm in ['administrator', 'manage_guild', 'manage_roles', 'manage_channels', 'view_audit_log']:
                admin_perms.append(f"• {desc}")
            elif perm in ['kick_members', 'ban_members', 'moderate_members', 'manage_messages', 'manage_nicknames']:
                moderation_perms.append(f"• {desc}")
            elif 'message' in perm or 'thread' in perm or 'embed' in perm or 'reaction' in perm or 'emoji' in perm or 'sticker' in perm:
                text_perms.append(f"• {desc}")
            elif 'voice' in perm or 'speak' in perm or 'stream' in perm or 'sound' in perm or 'mute' in perm or 'deafen' in perm or 'connect' in perm or 'move' in perm:
                voice_perms.append(f"• {desc}")
            else:
                other_perms.append(f"• {desc}")
        
        # Add sections
        if admin_perms:
            embed.add_field(
                name="⚙️ Administrative Permissions",
                value="\n".join(admin_perms[:10]),
                inline=False
            )
        
        if moderation_perms:
            embed.add_field(
                name="🛡️ Moderation Permissions",
                value="\n".join(moderation_perms[:10]),
                inline=False
            )
        
        if text_perms:
            # Split if too many
            if len(text_perms) > 10:
                embed.add_field(
                    name="💬 Text Channel Permissions (1/2)",
                    value="\n".join(text_perms[:10]),
                    inline=False
                )
                embed.add_field(
                    name="💬 Text Channel Permissions (2/2)",
                    value="\n".join(text_perms[10:20]),
                    inline=False
                )
            else:
                embed.add_field(
                    name="💬 Text Channel Permissions",
                    value="\n".join(text_perms),
                    inline=False
                )
        
        if voice_perms:
            embed.add_field(
                name="🔊 Voice Channel Permissions",
                value="\n".join(voice_perms[:10]),
                inline=False
            )
        
        if other_perms:
            embed.add_field(
                name="🔧 Other Permissions",
                value="\n".join(other_perms[:10]),
                inline=False
            )
    else:
        embed.add_field(
            name="🔑 Permissions",
            value="This role has no special permissions.",
            inline=False
        )
    
    # Member list (first 10)
    if member_count > 0:
        members = role.members[:10]
        member_list = ", ".join([m.mention for m in members])
        if member_count > 10:
            member_list += f"\n... and {member_count - 10} more"
        
        embed.add_field(
            name=f"👥 Members ({member_count} total)",
            value=member_list,
            inline=False
        )
    
    embed.set_footer(text=f"Role created")
    
    await ctx.send(embed=embed)


@bot.command(name="rolehelp", help="Show help for role information commands")
async def rolehelp_cmd(ctx: commands.Context):
    """Show help for role commands."""
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Role Information Commands",
        description="Learn about server roles and their permissions.",
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.add_field(
        name="📋 ?roles",
        value="Show a simple list of all server roles with member counts.\n"
              "**Example:** `?roles`",
        inline=False
    )
    
    embed.add_field(
        name="🔍 ?roleinfo [@role]",
        value="Show role information with key permissions (short format).\n"
              "• No mention: Shows top 10 roles\n"
              "• With mention: Shows specific role details\n"
              "**Example:** `?roleinfo @Staff`",
        inline=False
    )
    
    embed.add_field(
        name="📖 ?rolefullinfo @role",
        value="Show COMPLETE role information with ALL permissions explained.\n"
              "Requires a role mention.\n"
              "**Example:** `?rolefullinfo @Moderator`",
        inline=False
    )
    
    embed.add_field(
        name="🔒 Permissions",
        value="These commands are **staff-only** (Moderator+ permissions required).",
        inline=False
    )
    
    embed.set_footer(text="United Bunnies Role System")
    
    await ctx.send(embed=embed)
