"""
Servicios para obtener datos de NBA usando nba_api
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

from nba_api.stats.endpoints import LeagueGameFinder, BoxScoreTraditionalV2, ScoreboardV2
from nba_api.stats.static import players, teams
from django.db import transaction
from django.utils import timezone

from .models import NBATeam, NBAPlayer, NBAGame


class NBADataService:
    """Servicio principal para obtener datos de NBA"""
    
    def __init__(self):
        self.request_delay = 1.0  # Delay entre requests para evitar rate limiting
    
    def _delay_request(self):
        """Pausa entre requests"""
        time.sleep(self.request_delay)
    
    def sync_teams(self) -> Dict[str, int]:
        """Sincroniza equipos de NBA"""
        print("🔄 Sincronizando equipos NBA...")
        
        try:
            nba_teams = teams.get_teams()
            created_count = 0
            updated_count = 0
            
            for team_data in nba_teams:
                team, created = NBATeam.objects.get_or_create(
                    nba_id=team_data['id'],
                    defaults={
                        'full_name': team_data['full_name'],
                        'abbreviation': team_data['abbreviation'],
                        'nickname': team_data['nickname'],
                        'city': team_data['city'],
                        'state': team_data['state'],
                        'year_founded': team_data['year_founded'],
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Actualizar datos existentes
                    team.full_name = team_data['full_name']
                    team.abbreviation = team_data['abbreviation']
                    team.nickname = team_data['nickname']
                    team.city = team_data['city']
                    team.state = team_data['state']
                    team.year_founded = team_data['year_founded']
                    team.save()
                    updated_count += 1
            
            print(f"✅ Equipos sincronizados: {created_count} creados, {updated_count} actualizados")
            return {'created': created_count, 'updated': updated_count}
            
        except Exception as e:
            print(f"❌ Error sincronizando equipos: {e}")
            return {'error': str(e)}
    
    def sync_players(self) -> Dict[str, int]:
        """Sincroniza jugadores de NBA"""
        print("🔄 Sincronizando jugadores NBA...")
        
        try:
            nba_players = players.get_players()
            created_count = 0
            updated_count = 0
            
            for player_data in nba_players:
                player, created = NBAPlayer.objects.get_or_create(
                    nba_id=player_data['id'],
                    defaults={
                        'full_name': player_data['full_name'],
                        'first_name': player_data['first_name'],
                        'last_name': player_data['last_name'],
                        'is_active': player_data['is_active'],
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Actualizar datos existentes
                    player.full_name = player_data['full_name']
                    player.first_name = player_data['first_name']
                    player.last_name = player_data['last_name']
                    player.is_active = player_data['is_active']
                    player.save()
                    updated_count += 1
            
            print(f"✅ Jugadores sincronizados: {created_count} creados, {updated_count} actualizados")
            return {'created': created_count, 'updated': updated_count}
            
        except Exception as e:
            print(f"❌ Error sincronizando jugadores: {e}")
            return {'error': str(e)}
    
    def get_games_by_season(self, season: str = "2025-26") -> pd.DataFrame:
        """Obtiene partidos de una temporada específica"""
        print(f"🔄 Obteniendo partidos de la temporada {season}...")
        
        try:
            self._delay_request()
            gamefinder = LeagueGameFinder(season_nullable=season, league_id_nullable="00")
            games_df = gamefinder.get_data_frames()[0]
            
            print(f"✅ Obtenidos {len(games_df)} partidos de la temporada {season}")
            return games_df
            
        except Exception as e:
            print(f"❌ Error obteniendo partidos: {e}")
            return pd.DataFrame()
    
    def get_recent_games(self, days: int = 7) -> pd.DataFrame:
        """Obtiene partidos recientes"""
        print(f"🔄 Obteniendo partidos de los últimos {days} días...")
        
        try:
            self._delay_request()
            scoreboard = ScoreboardV2()
            games_df = scoreboard.get_data_frames()[0]
            
            print(f"✅ Obtenidos {len(games_df)} partidos recientes")
            return games_df
            
        except Exception as e:
            print(f"❌ Error obteniendo partidos recientes: {e}")
            return pd.DataFrame()
    
    def sync_games_from_dataframe(self, games_df: pd.DataFrame) -> Dict[str, int]:
        """Sincroniza partidos desde un DataFrame"""
        print(f"🔄 Sincronizando {len(games_df)} partidos...")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        # Agrupar por GAME_ID para obtener datos de ambos equipos
        games_grouped = games_df.groupby('GAME_ID')
        
        for game_id, game_data in games_grouped:
            try:
                if len(game_data) != 2:
                    print(f"⚠️ Partido {game_id} tiene {len(game_data)} registros, esperado 2")
                    continue
                
                # Separar datos de local y visitante
                home_data = game_data[game_data['MATCHUP'].str.contains('vs.')].iloc[0]
                away_data = game_data[game_data['MATCHUP'].str.contains('@')].iloc[0]
                
                # Obtener equipos
                try:
                    home_team = NBATeam.objects.get(nba_id=home_data['TEAM_ID'])
                    away_team = NBATeam.objects.get(nba_id=away_data['TEAM_ID'])
                except NBATeam.DoesNotExist:
                    print(f"⚠️ Equipo no encontrado para partido {game_id}")
                    error_count += 1
                    continue
                
                # Crear o actualizar partido
                game_date = datetime.strptime(home_data['GAME_DATE'], '%Y-%m-%d').date()
                
                game, created = NBAGame.objects.get_or_create(
                    nba_game_id=game_id,
                    defaults={
                        'season_id': home_data['SEASON_ID'],
                        'game_date': game_date,
                        'season_type': home_data.get('SEASON_TYPE', 'Regular Season'),
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_win': home_data['WL'] == 'W',
                        'home_points': int(home_data['PTS']) if pd.notna(home_data['PTS']) else None,
                        'away_points': int(away_data['PTS']) if pd.notna(away_data['PTS']) else None,
                        # Estadísticas del equipo local
                        'home_minutes': int(home_data['MIN']) if pd.notna(home_data['MIN']) else None,
                        'home_fgm': int(home_data['FGM']) if pd.notna(home_data['FGM']) else None,
                        'home_fga': int(home_data['FGA']) if pd.notna(home_data['FGA']) else None,
                        'home_fg_pct': float(home_data['FG_PCT']) if pd.notna(home_data['FG_PCT']) else None,
                        'home_fg3m': int(home_data['FG3M']) if pd.notna(home_data['FG3M']) else None,
                        'home_fg3a': int(home_data['FG3A']) if pd.notna(home_data['FG3A']) else None,
                        'home_fg3_pct': float(home_data['FG3_PCT']) if pd.notna(home_data['FG3_PCT']) else None,
                        'home_ftm': int(home_data['FTM']) if pd.notna(home_data['FTM']) else None,
                        'home_fta': int(home_data['FTA']) if pd.notna(home_data['FTA']) else None,
                        'home_ft_pct': float(home_data['FT_PCT']) if pd.notna(home_data['FT_PCT']) else None,
                        'home_oreb': int(home_data['OREB']) if pd.notna(home_data['OREB']) else None,
                        'home_dreb': int(home_data['DREB']) if pd.notna(home_data['DREB']) else None,
                        'home_reb': int(home_data['REB']) if pd.notna(home_data['REB']) else None,
                        'home_ast': int(home_data['AST']) if pd.notna(home_data['AST']) else None,
                        'home_stl': int(home_data['STL']) if pd.notna(home_data['STL']) else None,
                        'home_blk': int(home_data['BLK']) if pd.notna(home_data['BLK']) else None,
                        'home_tov': int(home_data['TOV']) if pd.notna(home_data['TOV']) else None,
                        'home_pf': int(home_data['PF']) if pd.notna(home_data['PF']) else None,
                        'home_plus_minus': int(home_data['PLUS_MINUS']) if pd.notna(home_data['PLUS_MINUS']) else None,
                        # Estadísticas del equipo visitante
                        'away_minutes': int(away_data['MIN']) if pd.notna(away_data['MIN']) else None,
                        'away_fgm': int(away_data['FGM']) if pd.notna(away_data['FGM']) else None,
                        'away_fga': int(away_data['FGA']) if pd.notna(away_data['FGA']) else None,
                        'away_fg_pct': float(away_data['FG_PCT']) if pd.notna(away_data['FG_PCT']) else None,
                        'away_fg3m': int(away_data['FG3M']) if pd.notna(away_data['FG3M']) else None,
                        'away_fg3a': int(away_data['FG3A']) if pd.notna(away_data['FG3A']) else None,
                        'away_fg3_pct': float(away_data['FG3_PCT']) if pd.notna(away_data['FG3_PCT']) else None,
                        'away_ftm': int(away_data['FTM']) if pd.notna(away_data['FTM']) else None,
                        'away_fta': int(away_data['FTA']) if pd.notna(away_data['FTA']) else None,
                        'away_ft_pct': float(away_data['FT_PCT']) if pd.notna(away_data['FT_PCT']) else None,
                        'away_oreb': int(away_data['OREB']) if pd.notna(away_data['OREB']) else None,
                        'away_dreb': int(away_data['DREB']) if pd.notna(away_data['DREB']) else None,
                        'away_reb': int(away_data['REB']) if pd.notna(away_data['REB']) else None,
                        'away_ast': int(away_data['AST']) if pd.notna(away_data['AST']) else None,
                        'away_stl': int(away_data['STL']) if pd.notna(away_data['STL']) else None,
                        'away_blk': int(away_data['BLK']) if pd.notna(away_data['BLK']) else None,
                        'away_tov': int(away_data['TOV']) if pd.notna(away_data['TOV']) else None,
                        'away_pf': int(away_data['PF']) if pd.notna(away_data['PF']) else None,
                        'away_plus_minus': int(away_data['PLUS_MINUS']) if pd.notna(away_data['PLUS_MINUS']) else None,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
                # Pausa para evitar rate limiting
                if (created_count + updated_count) % 10 == 0:
                    self._delay_request()
                
            except Exception as e:
                print(f"❌ Error procesando partido {game_id}: {e}")
                error_count += 1
                continue
        
        print(f"✅ Partidos sincronizados: {created_count} creados, {updated_count} actualizados, {error_count} errores")
        return {'created': created_count, 'updated': updated_count, 'errors': error_count}
    
    def sync_current_season_games(self, season: str = "2025-26") -> Dict[str, int]:
        """Sincroniza partidos de la temporada indicada"""
        print(f"🔄 Sincronizando partidos de la temporada {season}...")
        
        # Obtener partidos de la temporada actual
        games_df = self.get_games_by_season(season)
        
        if games_df.empty:
            return {'error': 'No se pudieron obtener partidos'}
        
        # Sincronizar en la base de datos
        return self.sync_games_from_dataframe(games_df)
    
    def get_team_stats(self, team_id: str, season: str = "2024-25") -> Dict:
        """Obtiene estadísticas de un equipo específico"""
        try:
            self._delay_request()
            gamefinder = LeagueGameFinder(team_id_nullable=team_id, season_nullable=season)
            games_df = gamefinder.get_data_frames()[0]
            
            if games_df.empty:
                return {}
            
            # Calcular estadísticas promedio
            stats = {
                'games_played': len(games_df),
                'avg_points': games_df['PTS'].mean(),
                'avg_fg_pct': games_df['FG_PCT'].mean(),
                'avg_fg3_pct': games_df['FG3_PCT'].mean(),
                'avg_ft_pct': games_df['FT_PCT'].mean(),
                'avg_rebounds': games_df['REB'].mean(),
                'avg_assists': games_df['AST'].mean(),
                'avg_turnovers': games_df['TOV'].mean(),
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas del equipo {team_id}: {e}")
            return {}


# Instancia global del servicio
nba_service = NBADataService()
