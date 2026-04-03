export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.4"
  }
  public: {
    Tables: {
      backtest_runs: {
        Row: {
          algo_name: string | null
          created_at: string | null
          id: string
          round_id: string | null
          status: string | null
          total_pnl: number | null
        }
        Insert: {
          algo_name?: string | null
          created_at?: string | null
          id?: string
          round_id?: string | null
          status?: string | null
          total_pnl?: number | null
        }
        Update: {
          algo_name?: string | null
          created_at?: string | null
          id?: string
          round_id?: string | null
          status?: string | null
          total_pnl?: number | null
        }
        Relationships: []
      }
      internal: {
        Row: {
          backtest_id: string | null
          id: number
          timestamp: number | null
          order_price: number | null
          order_quantity: number | null
          product: string | null
          day: string | null
        }
        Insert: {
          backtest_id?: string | null
          id?: never
          order_price?: number | null
          order_quantity?: number | null
          product?: string | null
          timestamp?: number | null
        }
        Update: {
          backtest_id?: string | null
          id?: never
          order_price?: number | null
          order_quantity?: number | null
          product?: string | null
          timestamp?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "internal_backtest_id_fkey"
            columns: ["backtest_id"]
            isOneToOne: false
            referencedRelation: "backtest_runs"
            referencedColumns: ["id"]
          },
        ]
      }
      prices: {
        Row: {
          ask_price_1: number | null
          ask_price_2: number | null
          ask_price_3: number | null
          ask_volume_1: number | null
          ask_volume_2: number | null
          ask_volume_3: number | null
          backtest_id: string | null
          bid_price_1: number | null
          bid_price_2: number | null
          bid_price_3: number | null
          bid_volume_1: number | null
          bid_volume_2: number | null
          bid_volume_3: number | null
          day: number | null
          id: number
          mid_price: number | null
          product: string | null
          profit_and_loss: number | null
          timestamp: number | null
          wallmid1: number | null
          wallmid2: number | null
        }
        Insert: {
          ask_price_1?: number | null
          ask_price_2?: number | null
          ask_price_3?: number | null
          ask_volume_1?: number | null
          ask_volume_2?: number | null
          ask_volume_3?: number | null
          backtest_id?: string | null
          bid_price_1?: number | null
          bid_price_2?: number | null
          bid_price_3?: number | null
          bid_volume_1?: number | null
          bid_volume_2?: number | null
          bid_volume_3?: number | null
          day?: number | null
          id?: never
          mid_price?: number | null
          product?: string | null
          profit_and_loss?: number | null
          timestamp?: number | null
          wallmid1?: number | null
          wallmid2?: number | null
        }
        Update: {
          ask_price_1?: number | null
          ask_price_2?: number | null
          ask_price_3?: number | null
          ask_volume_1?: number | null
          ask_volume_2?: number | null
          ask_volume_3?: number | null
          backtest_id?: string | null
          bid_price_1?: number | null
          bid_price_2?: number | null
          bid_price_3?: number | null
          bid_volume_1?: number | null
          bid_volume_2?: number | null
          bid_volume_3?: number | null
          day?: number | null
          id?: never
          mid_price?: number | null
          product?: string | null
          profit_and_loss?: number | null
          timestamp?: number | null
          wallmid1?: number | null
          wallmid2?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "prices_backtest_id_fkey"
            columns: ["backtest_id"]
            isOneToOne: false
            referencedRelation: "backtest_runs"
            referencedColumns: ["id"]
          },
        ]
      }
      trades: {
        Row: {
          algo_position: number | null
          backtest_id: string | null
          buyer: string | null
          buyer_class: string | null
          currency: string | null
          day: number | null
          id: number
          price: number | null
          quantity: number | null
          seller: string | null
          seller_class: string | null
          symbol: string | null
          timestamp: number | null
        }
        Insert: {
          algo_position?: number | null
          backtest_id?: string | null
          buyer?: string | null
          buyer_class?: string | null
          currency?: string | null
          day?: number | null
          id?: never
          price?: number | null
          quantity?: number | null
          seller?: string | null
          seller_class?: string | null
          symbol?: string | null
          timestamp?: number | null
        }
        Update: {
          algo_position?: number | null
          backtest_id?: string | null
          buyer?: string | null
          buyer_class?: string | null
          currency?: string | null
          day?: number | null
          id?: never
          price?: number | null
          quantity?: number | null
          seller?: string | null
          seller_class?: string | null
          symbol?: string | null
          timestamp?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "trades_backtest_id_fkey"
            columns: ["backtest_id"]
            isOneToOne: false
            referencedRelation: "backtest_runs"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
